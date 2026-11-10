import pytest
from fastapi.testclient import TestClient

from athena_api.app import create_app
from athena_api.lectures.cli import main as lectures_cli
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import MemoryLectureStore, SqliteLectureStore
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import MemorySessionStore
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore

OFF = "cse5alg-2026-s2"
URL = f"/units/{OFF}/lectures"


def clip(n, start, end, title="t", transcript="so insertion sort shifts larger elements right"):
    return {"id": f"rec-{n:02d}", "recordingId": "rec", "startS": start, "endS": end, "topicId": "insertion-sort",
            "topic": "Insertion Sort", "title": title, "summary": "s", "transcript": transcript, "approved": False}


FILE = {"recordingId": "rec", "title": "Insertion Sort", "durationS": 600.0, "status": "ready", "offeringId": OFF,
        "week": 2, "media": "../x.mp4", "clips": [clip(1, 10, 100, "Cards"), clip(2, 100, 200, "Worst case"), clip(3, 250, 300, "Shell")]}


@pytest.fixture(params=["memory", "sqlite"])
def setup(request, tmp_path):
    store = MemoryLectureStore() if request.param == "memory" else SqliteLectureStore(tmp_path / "l.db")
    service = LectureService(store)
    service.import_indexer_file(FILE)
    who = {"student": "alice", "lecturer": "dr-liu"}
    app = create_app(srs=SrsService(MemoryStore()), sessions=SessionService(MemorySessionStore()), lectures=service,
                     resolve_student=lambda _r: who["student"], resolve_lecturer=lambda _r, _o: who["lecturer"])
    return TestClient(app), service, who


def student_clips(client):
    [lecture] = client.get(URL).json()
    return lecture


def test_students_see_nothing_until_approved_and_never_transcripts(setup):
    client, _, _ = setup
    lecture = student_clips(client)
    assert lecture["clips"] == [] and lecture["under_review"] is True
    client.post(f"{URL}/rec/clips/rec-02/status", json={"status": "approved"})
    lecture = student_clips(client)
    assert [c["title"] for c in lecture["clips"]] == ["Worst case"]
    assert "transcript" not in lecture["clips"][0]


def test_lecturer_review_routes_and_auth(setup):
    client, _, who = setup
    [lecture] = client.get(f"{URL}/review").json()
    assert [c["status"] for c in lecture["clips"]] == ["pending"] * 3
    assert client.post(f"{URL}/rec/approve-pending").json() == {"approved": 3}
    client.post(f"{URL}/rec/clips/rec-03/status", json={"status": "rejected"})
    assert [c["title"] for c in student_clips(client)["clips"]] == ["Cards", "Worst case"]
    who["lecturer"] = None
    assert client.get(f"{URL}/review").status_code == 403
    assert client.post(f"{URL}/rec/clips/rec-01/status", json={"status": "approved"}).status_code == 403


def test_edit_validates_and_approves_pending(setup):
    client, _, _ = setup
    ok = client.patch(f"{URL}/rec/clips/rec-03", json={"title": "Shell sort intro", "start_s": 240, "end_s": 310})
    assert ok.status_code == 204
    [c] = student_clips(client)["clips"]
    assert (c["title"], c["start_s"], c["end_s"]) == ("Shell sort intro", 240, 310)
    for body, why in [
        ({"title": "x", "start_s": 50, "end_s": 120}, "overlap"),
        ({"title": "x", "start_s": 300, "end_s": 290}, "after the start"),
        ({"title": "x", "start_s": 500, "end_s": 900}, "within the lecture"),
        ({"title": " ", "start_s": 240, "end_s": 300}, "title"),
    ]:
        r = client.patch(f"{URL}/rec/clips/rec-03", json=body)
        assert r.status_code == 422 and why in r.json()["detail"]


def test_undo_resets_decision_and_edits(setup):
    client, _, _ = setup
    client.patch(f"{URL}/rec/clips/rec-03", json={"title": "Renamed", "start_s": 240, "end_s": 310})
    client.delete(f"{URL}/rec/clips/rec-03/review")
    c = client.get(f"{URL}/review").json()[0]["clips"][2]
    assert (c["status"], c["title"], c["decided"]) == ("pending", "Shell", False)


def test_reimport_keeps_review_of_unchanged_clips_only(setup):
    client, service, _ = setup
    client.post(f"{URL}/rec/approve-pending")
    changed = {**FILE, "clips": [clip(1, 10, 100, "Cards"), clip(2, 100, 220, "Worst case, longer"), clip(3, 250, 300, "Shell")]}
    service.import_indexer_file(changed)
    statuses = [c["status"] for c in client.get(f"{URL}/review").json()[0]["clips"]]
    assert statuses == ["approved", "pending", "approved"]


def test_approved_material_includes_transcripts_for_the_tutor(setup):
    client, service, _ = setup
    client.post(f"{URL}/rec/clips/rec-01/status", json={"status": "approved"})
    [(lecture, clip_, transcript)] = service.approved_material(OFF)
    assert clip_["id"] == "rec-01" and "insertion sort" in transcript


def test_cli_imports(tmp_path, capsys):
    import json

    f = tmp_path / "clips.json"
    f.write_text(json.dumps(FILE))
    lectures_cli(["--db", str(tmp_path / "a.db"), "import", str(f)])
    assert "3 clips (3 pending review)" in capsys.readouterr().out
