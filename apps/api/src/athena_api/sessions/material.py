"""Which unit material a learning session gets: keyword-ranked approved lecture clips.

When a session starts, the student's goal is matched against every approved clip
of the unit (title, summary and transcript) with BM25 keyword ranking, and the
best few go to the agent as materials (agent VideoSegment items). Only approved
clips are ever used: unapproved ones are unreviewed AI output.

Embeddings (matching by meaning) can replace the ranking later behind the same interface.
"""

import math
import re
from collections import Counter
from typing import Protocol

from ..lectures.service import LectureService

MAX_CLIPS = 5
#: How much more a match in a clip's title/summary counts than one in its transcript.
ABOUT_WEIGHT = 3.0

_STOP = set(
    "a an and are as at be but by do does for from how i in is it its me of on or so that the this to was what when "
    "which why will with you your about learn understand explain help want know".split()
)


def _stem(w: str) -> str:
    """Tiny suffix stripper, consistent across forms:
    reverse/reversed/reverses → revers, sort/sorted/sorting/sorts → sort, class/classes → class."""
    if len(w) > 4:
        w = re.sub(r"(ing|ed|es|(?<!s)s)$", "", w)
    elif len(w) > 3:
        w = re.sub(r"(?<!s)s$", "", w)
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    return w


def _terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9²]+", text.lower())
    return [_stem(w) for w in words if len(w) > 1 and w not in _STOP]


def rank(goal: str, docs: list[str], *, k1: float = 1.2, b: float = 0.75) -> list[float]:
    """BM25 score of each doc for the goal (0 = no shared terms)."""
    query = set(_terms(goal))
    tokenised = [_terms(d) for d in docs]
    if not query or not tokenised:
        return [0.0] * len(docs)
    avg = sum(len(t) for t in tokenised) / len(tokenised) or 1
    df = Counter(term for t in tokenised for term in set(t))
    n = len(tokenised)
    scores = []
    for t in tokenised:
        tf = Counter(t)
        score = 0.0
        for q in query:
            if tf[q]:
                idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
                score += idf * tf[q] * (k1 + 1) / (tf[q] + k1 * (1 - b + b * len(t) / avg))
        scores.append(score)
    return scores


def _scaled(scores: list[float]) -> list[float]:
    top = max(scores, default=0.0)
    return [s / top for s in scores] if top > 0 else scores


class MaterialProvider(Protocol):
    def for_goal(self, offering_id: str, goal: str) -> list[dict]:
        """Agent retrieval items (VideoSegment dicts) for a session's goal; may be empty."""
        ...


class LectureMaterial:
    def __init__(self, lectures: LectureService, *, max_clips: int = MAX_CLIPS):
        self.lectures = lectures
        self.max_clips = max_clips

    def for_goal(self, offering_id: str, goal: str) -> list[dict]:
        material = self.lectures.approved_material(offering_id)
        # Title and summary say what a clip is *about*; transcripts mostly add volume
        # (every sorting clip says "sort" a lot). So they're ranked separately and weighted.
        about = rank(goal, [f"{c['title']} {c['summary']}" for _, c, _ in material])
        spoken = rank(goal, [t for _, _, t in material])
        # Scale each to 0-1 first, so the weight means the same whatever the transcript lengths.
        about, spoken = _scaled(about), _scaled(spoken)
        scores = [ABOUT_WEIGHT * a + b for a, b in zip(about, spoken, strict=True)]
        scored = sorted(zip(scores, material, strict=True), key=lambda x: -x[0])
        return [
            {
                "kind": "video",
                "source_id": lecture.id,
                "segment_id": clip["id"],
                "title": f"Week {lecture.week}: {clip['title']}" if lecture.week else clip["title"],
                "transcript": transcript,
                "start_seconds": clip["start_s"],
                "end_seconds": clip["end_s"],
            }
            for score, (lecture, clip, transcript) in scored[: self.max_clips]
            if score > 0
        ]


class OfferingMaterial:
    """One offering-scoped ranking interface for immutable passages and approved clips."""
    def __init__(self, materials, lectures: LectureService, max_results=5):
        self.materials, self.lectures, self.max_results = materials, lectures, max_results

    def for_goal(self, offering_id: str, goal: str) -> list[dict]:
        catalog = self.materials.list(offering_id, manager=True)
        approved = self.lectures.approved_material(offering_id)
        approved_recordings = {lecture.id for lecture, _, _ in approved}
        selected = {}
        for material in catalog:
            usable = material['status'] == 'ready' and (
                material['kind'] == 'document' and material['published'] or
                material['kind'] == 'recording' and material['id'] in approved_recordings)
            if usable and material['version'] > selected.get(material['source_id'], {}).get('version', 0):
                selected[material['source_id']] = material
        active = {m['id'] for m in selected.values()}
        known = {m['id'] for m in catalog}
        items = []
        for material in selected.values():
            if material['kind'] != 'document':
                continue
            for passage in self.materials.passages(offering_id, material['id']):
                items.append(dict(kind='document', source_id=material['id'], passage_id=passage['id'],
                                  title=f"{material['filename']} · v{material['version']}", text=passage['text'],
                                  page=passage['page'], section=passage['section']))
        for lecture, clip, text in approved:
            if lecture.id in known and lecture.id not in active:
                continue
            items.append(dict(kind='video', source_id=lecture.id, segment_id=clip['id'], title=clip['title'],
                              transcript=text, start_seconds=clip['start_s'], end_seconds=clip['end_s']))
        about = _scaled(rank(goal, [i['title'] for i in items]))
        body = _scaled(rank(goal, [i.get('text', i.get('transcript', '')) for i in items]))
        scored = sorted(zip([ABOUT_WEIGHT * a + b for a, b in zip(about, body, strict=True)], items, strict=True), key=lambda pair: -pair[0])
        result = []
        for score, item in scored[:self.max_results]:
            if score <= 0:
                continue
            if item['kind'] == 'video' and len(item['transcript']) > 6000:
                text = item['transcript']
                positions = [text.lower().find(term) for term in re.findall(r'[a-z]{4,}', goal.lower())]
                at = min((p for p in positions if p >= 0), default=0)
                start = max(0, min(at - 1000, len(text) - 6000))
                item = {**item, 'transcript': text[start:start + 6000]}
            result.append(item)
        return result
