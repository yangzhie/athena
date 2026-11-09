"""Step 4: transcript → numbered, sentence-sized lines the LLM can cite by index.

Whisper segments don't line up with sentences: one segment can hold several
sentences, or a sentence can run across two. This splits segments at sentence
ends (estimating times inside a segment by text length), joins pieces back into
whole sentences, and keeps lines a useful size: not single filler words, not
minute-long monologues.
"""

import re

from .models import Line, Transcript, TranscriptSegment

MIN_WORDS = 4  # shorter pieces ("OK.", "Uh, right.") join the next line
MAX_LINE_S = 30.0  # a line never runs longer than this
PAUSE_S = 2.0  # a silence this long always ends a line

# A sentence ends at . ? ! (optionally followed by a closing quote/bracket), then whitespace.
_SENTENCE_END = re.compile(r"""[.?!]["')\]]?(?=\s)""")
# Words ending in "." that don't end a sentence.
_ABBREVIATIONS = {"e.g.", "i.e.", "etc.", "vs.", "dr.", "mr.", "ms.", "mrs.", "prof.", "approx."}


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    parts, start = [], 0
    for m in _SENTENCE_END.finditer(text):
        word = text[:m.start() + 1].rsplit(maxsplit=1)[-1].lower()
        if word in _ABBREVIATIONS:
            continue
        parts.append(text[start:m.end()].strip())
        start = m.end()
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def _ends_sentence(text: str) -> bool:
    return bool(re.search(r"""[.?!]["')\]]?$""", text))


def _pieces(segments: list[TranscriptSegment]) -> list[tuple[float, float, str]]:
    """Split each segment at sentence ends, sharing its time span by character count."""
    out = []
    for seg in segments:
        sentences = split_sentences(seg.text)
        total = sum(len(s) for s in sentences) or 1
        t = seg.start_s
        span = seg.end_s - seg.start_s
        for s in sentences:
            end = t + span * len(s) / total
            out.append((t, end, s))
            t = end
    return out


def to_lines(
    transcript: Transcript,
    *,
    min_words: int = MIN_WORDS,
    max_line_s: float = MAX_LINE_S,
    pause_s: float = PAUSE_S,
) -> list[Line]:
    """Numbered lines covering the whole transcript, in order, starting at index 0."""
    lines: list[Line] = []
    buf: list[tuple[float, float, str]] = []

    def flush() -> None:
        if buf:
            text = " ".join(t for _, _, t in buf)
            lines.append(Line(index=len(lines), start_s=buf[0][0], end_s=buf[-1][1], text=text))
            buf.clear()

    for start, end, text in _pieces(transcript.segments):
        if buf:
            gap = start - buf[-1][1]
            too_long = end - buf[0][0] > max_line_s
            if gap >= pause_s or too_long:
                flush()
        buf.append((start, end, text))
        words = sum(len(t.split()) for _, _, t in buf)
        if _ends_sentence(text) and words >= min_words:
            flush()
    flush()
    return lines


def _clock(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def render(lines: list[Line]) -> str:
    """Compact text for the LLM: one line per Line, `index [mm:ss] text`.

    Times are there to help the model notice pauses and pacing; it answers with indices only.
    """
    return "\n".join(f"{line.index} [{_clock(line.start_s)}] {line.text}" for line in lines)
