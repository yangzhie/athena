import asyncio

from athena_api.lectures.service import LectureService
from athena_api.lectures.store import MemoryLectureStore
from athena_api.sessions.agent_tutor import AgentTutor
from athena_api.sessions.material import LectureMaterial, rank
from athena_api.sessions.models import LearningSession

OFF = "cse5alg-2026-s2"


def clip(n, title, summary, transcript, start):
    return {"id": f"rec-{n:02d}", "recordingId": "rec", "startS": start, "endS": start + 120, "topicId": "insertion-sort",
            "topic": "Insertion Sort", "title": title, "summary": summary, "transcript": transcript}


def lectures(approve=True):
    service = LectureService(MemoryLectureStore())
    service.import_indexer_file({
        "recordingId": "rec", "title": "Insertion Sort", "durationS": 6600.0, "status": "ready", "offeringId": OFF, "week": 2,
        "clips": [
            clip(1, "Insertion sort through playing cards", "Sorting cards in your hand.", "so think of a hand of cards", 41),
            clip(2, "Worst-case insertion sort complexity", "Reversed input is the worst case.",
                 "if the array is in reverse order every element shifts so it is n squared", 1421),
            clip(3, "Shell and Knuth gap sequences", "Choosing gaps for shell sort.", "the gap sequence decides the running time", 4281),
        ],
    })
    if approve:
        service.approve_pending(OFF, "rec")
    return service


def test_rank_prefers_matching_documents():
    scores = rank("worst case of insertion sort", ["playing cards", "worst case insertion sort reversed", "gap sequence"])
    assert scores[1] > scores[0] and scores[2] == 0


def test_material_ranks_approved_clips_for_the_goal():
    items = LectureMaterial(lectures()).for_goal(OFF, "Why is insertion sort slow on reversed input?")
    assert items[0]["segment_id"] == "rec-02"
    assert items[0]["kind"] == "video" and items[0]["source_id"] == "rec"
    assert items[0]["title"] == "Week 2: Worst-case insertion sort complexity"
    assert "n squared" in items[0]["transcript"]
    assert items[-1]["segment_id"] == "rec-03"  # only shares "sort": included, ranked last


def test_unapproved_clips_are_never_material():
    assert LectureMaterial(lectures(approve=False)).for_goal(OFF, "insertion sort worst case") == []


def test_unrelated_goal_gets_no_material():
    assert LectureMaterial(lectures()).for_goal(OFF, "Dijkstra shortest paths") == []


def test_title_and_summary_outweigh_long_transcripts():
    service = LectureService(MemoryLectureStore())
    long_talk = "insertion sort " * 40 + "array " * 40
    service.import_indexer_file({
        "recordingId": "rec", "title": "L", "durationS": 6600.0, "status": "ready", "offeringId": OFF,
        "clips": [
            clip(1, "Shell sort gaps", "Gapped insertion sort passes.", long_talk, 100),
            clip(2, "Worst-case insertion sort complexity", "Reverse-sorted input gives quadratic time.", "n squared", 400),
        ],
    })
    service.approve_pending(OFF, "rec")
    items = LectureMaterial(service).for_goal(OFF, "Why is insertion sort slow on reversed arrays?")
    assert items[0]["segment_id"] == "rec-02"


def test_max_clips():
    assert len(LectureMaterial(lectures(), max_clips=1).for_goal(OFF, "insertion sort shell sort cards")) == 1


def test_agent_tutor_starts_the_agent_with_the_materials():
    seen = {}

    class FakeOrchestrator:
        async def start(self, context, goal, *, materials=None, capabilities=None):
            seen["goal"], seen["materials"] = goal, materials
            raise RuntimeError("stop here")

    tutor = AgentTutor(store=None, llm=None, material=LectureMaterial(lectures()))
    tutor._orchestrator = lambda _s: FakeOrchestrator()
    session = LearningSession(id="s1", student_id="alice", offering_id=OFF, goal="insertion sort worst case",
                              title="t", created_at=__import__("datetime").datetime(2026, 11, 10), updated_at=__import__("datetime").datetime(2026, 11, 10))
    try:
        asyncio.run(tutor.start(session))
    except RuntimeError:
        pass
    assert seen["goal"] == "insertion sort worst case"
    assert seen["materials"].items[0].segment_id == "rec-02"


def test_start_falls_back_to_no_materials_when_agent_finds_them_insufficient():
    import datetime

    from athena_agent.learning import QuestionActivity
    from athena_api.sessions.tutor import TutorError

    calls = []
    question = QuestionActivity.model_validate({
        "activity_id": "a1", "question": {"kind": "open_ended", "question_id": "q1", "concept_id": "c",
                                          "prompt": "What do you know about it?", "difficulty": "beginner"}})

    class FakeOrchestrator:
        async def start(self, context, goal, *, materials=None, capabilities=None):
            calls.append(materials)
            if materials is not None:
                err = RuntimeError("insufficient")
                err.code = "insufficient_evidence"
                raise err
            return question

    tutor = AgentTutor(store=None, llm=None, material=LectureMaterial(lectures()))
    tutor._orchestrator = lambda _s: FakeOrchestrator()
    now = datetime.datetime(2026, 11, 10)
    session = LearningSession(id="s1", student_id="alice", offering_id=OFF, goal="insertion sort worst case",
                              title="t", created_at=now, updated_at=now)
    [reply] = asyncio.run(tutor.start(session))
    assert calls[0] is not None and calls[1] is None
    assert reply.content == "What do you know about it?"
    assert reply.knowledge_origin == 'general' and reply.sources == []
    assert TutorError  # imported for clarity: 409s trigger the fallback


def test_agent_context_budget_is_raised_and_configurable(monkeypatch):
    assert AgentTutor(store=None, llm=None).context_budget.context_window == 131_072
    monkeypatch.setenv("ATHENA_AGENT_CONTEXT_BYTES", "65536")
    assert AgentTutor(store=None, llm=None).context_budget.context_window == 65_536
