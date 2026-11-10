"""Lecture use cases: import from the indexer, student view, lecturer review, agent material."""

from dataclasses import dataclass
from pathlib import Path

from .models import (
    ClipReview,
    IndexerFile,
    Lecture,
    LecturerClip,
    LecturerLecture,
    ProposedClip,
    ReviewStatus,
    StoredClip,
    StudentClip,
    StudentLecture,
)
from .store import LectureStore


class NotFound(LookupError):
    pass


class Invalid(ValueError):
    pass


def _same(a: ProposedClip, b: ProposedClip) -> bool:
    keys = ("start_s", "end_s", "title", "topic_id", "summary")
    return all(getattr(a, k) == getattr(b, k) for k in keys)


@dataclass
class LectureService:
    store: LectureStore

    # --- import ---------------------------------------------------------------------------

    def import_indexer_file(self, data: dict, offering_id: str | None = None, base_dir: Path | None = None) -> Lecture:
        """Add or replace a lecture from the indexer's clips.json.

        A re-indexed lecture keeps the lecturer's review of clips that are unchanged
        (same id, times, title, topic and summary). Changed or new clips start pending.
        `base_dir` is the clips.json folder, to find the recording it points to.
        """
        f = IndexerFile.model_validate(data)
        offering = offering_id or f.offering_id
        if not offering:
            raise Invalid("clips.json has no offeringId; pass one")
        old = {c.id: c for c in (self.store.get(offering, f.recording_id) or _empty(offering, f)).clips}
        clips = [
            StoredClip(proposed=p, review=old[p.id].review if p.id in old and _same(old[p.id].proposed, p) else ClipReview())
            for p in sorted(f.clips, key=lambda c: c.start_s)
        ]
        media = (base_dir / f.media).resolve() if base_dir and f.media else None
        lecture = Lecture(
            id=f.recording_id, offering_id=offering, title=f.title, week=f.week if f.week and f.week > 0 else None,
            duration_s=f.duration_s, status=f.status, clips=clips,
            media_path=str(media) if media and media.is_file() else None,
        )
        self.store.put(lecture)
        return lecture

    # --- students -------------------------------------------------------------------------

    def for_students(self, offering_id: str) -> list[StudentLecture]:
        """Approved clips only, edits applied, no transcripts."""
        return [
            StudentLecture(
                id=l.id, offering_id=l.offering_id, title=l.title, week=l.week, duration_s=l.duration_s,
                status=l.status,
                clips=sorted((StudentClip(**c.effective()) for c in l.clips if c.status == "approved"), key=lambda c: c.start_s),
                under_review=any(c.status == "pending" for c in l.clips),
                has_media=self._playable(l, for_students=True) is not None,
            )
            for l in self.store.list(offering_id)
        ]

    # --- agent material -------------------------------------------------------------------

    def approved_material(self, offering_id: str) -> list[tuple[Lecture, dict, str]]:
        """(lecture, effective clip, transcript) for every approved clip: what the tutor may use."""
        return [
            (l, c.effective(), c.proposed.transcript)
            for l in self.store.list(offering_id)
            for c in l.clips
            if c.status == "approved" and c.proposed.transcript.strip()
        ]

    # --- lecturers ------------------------------------------------------------------------

    def for_lecturers(self, offering_id: str) -> list[LecturerLecture]:
        return [
            LecturerLecture(
                id=l.id, offering_id=l.offering_id, title=l.title, week=l.week, duration_s=l.duration_s, status=l.status,
                clips=[
                    LecturerClip(
                        **c.effective(), status=c.status,
                        proposed={"title": c.proposed.title, "start_s": c.proposed.start_s, "end_s": c.proposed.end_s},
                        decided=c.review != ClipReview(),
                    )
                    for c in l.clips
                ],
                has_media=self._playable(l, for_students=False) is not None,
            )
            for l in self.store.list(offering_id)
        ]

    # --- media ----------------------------------------------------------------------------

    @staticmethod
    def _playable(lecture: Lecture, *, for_students: bool) -> Path | None:
        """The recording, if it exists and this audience may watch it.
        Students only once the lecturer has approved at least one clip."""
        if not lecture.media_path:
            return None
        if for_students and not any(c.status == "approved" for c in lecture.clips):
            return None
        path = Path(lecture.media_path)
        return path if path.is_file() else None

    def media(self, offering_id: str, lecture_id: str, *, for_students: bool) -> Path:
        lecture = self.store.get(offering_id, lecture_id)
        path = self._playable(lecture, for_students=for_students) if lecture else None
        if path is None:
            raise NotFound("no recording to play")
        return path

    def _update(self, offering_id: str, lecture_id: str, clip_id: str, fn) -> None:
        lecture = self.store.get(offering_id, lecture_id)
        if lecture is None or not any(c.id == clip_id for c in lecture.clips):
            raise NotFound("no such clip")
        clips = [c.model_copy(update={"review": fn(c, lecture)}) if c.id == clip_id else c for c in lecture.clips]
        self.store.put(lecture.model_copy(update={"clips": clips}))

    def set_status(self, offering_id: str, lecture_id: str, clip_id: str, status: ReviewStatus) -> None:
        self._update(offering_id, lecture_id, clip_id, lambda c, _l: c.review.model_copy(update={"status": status}))

    def edit(self, offering_id: str, lecture_id: str, clip_id: str, *, title: str, start_s: float, end_s: float) -> None:
        """Rename or retime. Counts as approval if the clip was pending."""

        def apply(c: StoredClip, lecture: Lecture) -> ClipReview:
            if not title.strip():
                raise Invalid("give the clip a title")
            if end_s <= start_s:
                raise Invalid("the end must be after the start")
            if start_s < 0 or end_s > lecture.duration_s + 1:
                raise Invalid("the clip must lie within the lecture")
            others = sorted((o.effective() for o in lecture.clips if o.id != c.id and o.status != "rejected"),
                            key=lambda o: o["start_s"])
            if any(o["start_s"] < end_s and start_s < o["end_s"] for o in others):
                raise Invalid("clips can't overlap their neighbours")
            status = "approved" if c.review.status == "pending" else c.review.status
            return ClipReview(status=status, title=title.strip(), start_s=start_s, end_s=end_s)

        self._update(offering_id, lecture_id, clip_id, apply)

    def reset(self, offering_id: str, lecture_id: str, clip_id: str) -> None:
        """Undo the lecturer's decision and edits."""
        self._update(offering_id, lecture_id, clip_id, lambda _c, _l: ClipReview())

    def approve_pending(self, offering_id: str, lecture_id: str) -> int:
        lecture = self.store.get(offering_id, lecture_id)
        if lecture is None:
            raise NotFound("no such lecture")
        count = sum(1 for c in lecture.clips if c.status == "pending")
        clips = [c.model_copy(update={"review": c.review.model_copy(update={"status": "approved"})}) if c.status == "pending" else c
                 for c in lecture.clips]
        self.store.put(lecture.model_copy(update={"clips": clips}))
        return count


def _empty(offering: str, f: IndexerFile) -> Lecture:
    return Lecture(id=f.recording_id, offering_id=offering, title=f.title, duration_s=f.duration_s, status=f.status)
