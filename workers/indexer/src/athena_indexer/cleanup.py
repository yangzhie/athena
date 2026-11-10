"""Step 6: LLM segments (line ranges) → final clips with times.

Boundaries already fall between sentences, because they're line boundaries.
This step makes the list tidy for students:
- short noise between two parts of the same topic (a "can everyone hear me?")
  is bridged, so one explanation isn't split in two;
- adjacent segments on the same topic and idea are merged;
- teaching segments too short to be useful are folded into a neighbour;
- remaining noise (admin, breaks, tangents) is dropped.
"""

from dataclasses import dataclass

from .models import Clip, IndexResult, Line, ProposedSegment, Topic

MIN_CLIP_S = 45.0  # shorter teaching segments join a neighbour
BRIDGE_NOISE_S = 30.0  # noise this short between same-topic segments is absorbed


@dataclass
class _Span:
    first: int
    last: int
    topic_id: str | None
    title: str
    summary: str
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def absorb(self, other: "_Span") -> None:
        """Extend over `other`; keep the title and summary of whichever was longer."""
        if other.duration_s > self.duration_s and other.topic_id is not None:
            self.title, self.summary = other.title, other.summary
        self.first, self.last = min(self.first, other.first), max(self.last, other.last)
        self.start_s, self.end_s = min(self.start_s, other.start_s), max(self.end_s, other.end_s)


def _spans(segments: list[ProposedSegment], lines: list[Line]) -> list[_Span]:
    return [
        _Span(s.first_line, s.last_line, s.topic_id, s.title, s.summary, lines[s.first_line].start_s, lines[s.last_line].end_s)
        for s in sorted(segments, key=lambda s: s.first_line)
    ]


def tidy(segments: list[ProposedSegment], lines: list[Line], *, min_clip_s: float = MIN_CLIP_S, bridge_noise_s: float = BRIDGE_NOISE_S) -> list[_Span]:
    spans = _spans(segments, lines)

    # 1. Bridge short noise between two segments of the same topic.
    i = 1
    while i < len(spans) - 1:
        prev, mid, nxt = spans[i - 1], spans[i], spans[i + 1]
        if mid.topic_id is None and mid.duration_s <= bridge_noise_s and prev.topic_id is not None and prev.topic_id == nxt.topic_id:
            prev.absorb(mid)
            del spans[i]
        else:
            i += 1

    # 2. Drop noise.
    spans = [s for s in spans if s.topic_id is not None]

    # 3. Merge adjacent segments with the same topic and title (the model split one idea).
    merged: list[_Span] = []
    for s in spans:
        if merged and merged[-1].topic_id == s.topic_id and merged[-1].title.lower() == s.title.lower():
            merged[-1].absorb(s)
        else:
            merged.append(s)

    # 4. Fold too-short segments into a neighbour: same topic first, else the previous one.
    i = 0
    while i < len(merged) and len(merged) > 1:
        s = merged[i]
        if s.duration_s >= min_clip_s:
            i += 1
            continue
        prev = merged[i - 1] if i > 0 else None
        nxt = merged[i + 1] if i + 1 < len(merged) else None
        target = next((n for n in (prev, nxt) if n and n.topic_id == s.topic_id), prev or nxt)
        target.absorb(s)
        del merged[i]
        i = max(0, i - 1)
    return merged


def build_clips(
    segments: list[ProposedSegment],
    lines: list[Line],
    topics: list[Topic],
    *,
    recording_id: str,
    title: str,
    duration_s: float,
    offering_id: str | None = None,
    week: int | None = None,
    media: str | None = None,
    min_clip_s: float = MIN_CLIP_S,
    bridge_noise_s: float = BRIDGE_NOISE_S,
) -> IndexResult:
    """The finished clips.json content. Clips start unapproved; a lecturer approves them."""
    names = {t.id: t.name for t in topics}
    clips = [
        Clip(
            id=f"{recording_id}-{n:02d}",
            recording_id=recording_id,
            start_s=s.start_s,
            end_s=s.end_s,
            topic_id=s.topic_id,
            topic=names[s.topic_id],
            title=s.title,
            summary=s.summary,
            transcript=" ".join(line.text for line in lines[s.first : s.last + 1]),
        )
        for n, s in enumerate(tidy(segments, lines, min_clip_s=min_clip_s, bridge_noise_s=bridge_noise_s), start=1)
    ]
    return IndexResult(
        recording_id=recording_id, title=title, duration_s=duration_s, status="ready",
        offering_id=offering_id, week=week, media=media, clips=clips,
    )
