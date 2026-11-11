#!/usr/bin/env python3
"""Seed the demo units (chemistry, physics, coding) through the real API.

    apps/api/.venv/bin/python scripts/seed-demo.py [--keep-pending]
    apps/api/.venv/bin/python scripts/seed-demo.py --sessions-for-cookie <your athena_session cookie>

Needs `npm run dev:all` running (the API and the material worker do the work).
For each unit in scripts/demo-units.json it:

1. downloads the openly licensed lecture PDF and recording into data/demo/downloads/
   (gitignored: course material is never committed);
2. acts as its own demo lecturer: redeems a one-time invite, creates the Offering,
   adds its topics and uploads the files, exactly like a lecturer in the browser;
3. waits for the worker to extract the PDF and to transcribe and segment the
   recording (a few minutes per lecture, plus a few model calls each);
4. publishes the materials, approves the proposed clips (unless --keep-pending)
   and publishes the Offering, so every student sees it.

With --sessions-for-cookie, it also starts each unit's demo learning sessions (its
`session_goals`) for *your* browser identity, so the demo opens with the tutor's first
question already there. Your cookie is used for those requests only and never saved.

With --sample-data, it instead writes invented, clearly labelled sample data: a class
cohort for each unit's lecturer Insights and, with --sessions-for-cookie, your own
Progress with confidence intervals. --remove-sample-data deletes it again.

Safe to re-run: progress is kept in data/demo/seed-state.json, and finished steps
are skipped. The demo lecturer's browser cookie is saved there too, so the
lecturer side can be shown live (see docs/demo-units.md).
"""

import argparse
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts/demo-units.json"
DATA = Path(os.environ.get("ATHENA_DATA_ROOT", ROOT / "data")).resolve()
DEMO = DATA / "demo"
DOWNLOADS = DEMO / "downloads"
STATE = DEMO / "seed-state.json"
COOKIE = "athena_session"


def log(msg: str) -> None:
    print(msg, flush=True)


# --- downloads ------------------------------------------------------------------------


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    log(f"  downloading {dest.name} …")
    req = urllib.request.Request(url, headers={"User-Agent": "athena-demo-seed/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total and done % (20 << 20) < (1 << 20):
                log(f"    {done / total:5.0%} of {total / 1e6:.0f} MB")
    tmp.replace(dest)
    return dest


# --- API client -------------------------------------------------------------------------


class Api:
    def __init__(self, base: str, token: str | None):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        if token:
            host = urllib.parse.urlsplit(self.base).hostname
            self.jar.set_cookie(http.cookiejar.Cookie(
                0, COOKIE, token, None, False, host, False, False, "/", True, False, None, False, None, None, {}))

    @property
    def token(self) -> str | None:
        return next((c.value for c in self.jar if c.name == COOKIE), None)

    def call(self, method: str, path: str, body=None, *, data: bytes | None = None, stream=None, size: int = 0,
             ok=(200, 201, 202, 204), headers: dict | None = None):
        headers = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if stream is not None:
            data = stream
            headers["Content-Type"] = "application/octet-stream"
            headers["Content-Length"] = str(size)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=600) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code in ok:
                return None
            detail = e.read().decode(errors="replace")[:300]
            raise SystemExit(f"seed-demo: {method} {path} → HTTP {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise SystemExit(f"seed-demo: the API at {self.base} isn't reachable ({e.reason}). Start it with `npm run dev:all`.") from None


# --- state ------------------------------------------------------------------------------


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"units": {}}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


# --- seeding ----------------------------------------------------------------------------


def become_lecturer(api: Api, state: dict) -> None:
    identity = api.call("GET", "/identity")
    state["lecturer_cookie"] = api.token
    save_state(state)
    if identity and identity.get("role") == "lecturer":
        return
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from athena_api.spaces.service import StudySpaces  # local administrator operation, like the CLI

    db = Path(os.environ.get("ATHENA_DB", DATA / "athena.db"))
    code = StudySpaces(db).create_lecturer_invite()
    api.call("POST", "/identity/lecturer-access", {"code": code})
    log("Demo lecturer identity ready.")


def wait_ready(api: Api, offering: str, material_id: str, name: str, timeout_s: int) -> dict:
    start = time.monotonic()
    last = None
    while True:
        rows = api.call("GET", f"/units/{offering}/materials") or []
        row = next((r for r in rows if r["id"] == material_id), None)
        status = row["status"] if row else "missing"
        if status != last:
            log(f"    {name}: {status}")
            last = status
        if status in ("ready", "failed", "missing"):
            return row or {}
        if time.monotonic() - start > timeout_s:
            raise SystemExit(f"seed-demo: {name} still {status} after {timeout_s // 60} min. Is the material worker running (npm run dev:all)? Re-run to resume.")
        time.sleep(10)


def seed_unit(api: Api, unit: dict, state: dict, *, keep_pending: bool, timeout_s: int) -> None:
    log(f"\n== {unit['code']} {unit['title']}")
    s = state["units"].setdefault(unit["code"], {"materials": {}})

    if not s.get("offering_id"):
        created = api.call("POST", "/offerings", {k: unit[k] for k in ("code", "title", "year", "semester")})
        s["offering_id"] = created["id"]
        save_state(state)
        log(f"  created Offering {created['id']}")
    offering = s["offering_id"]

    existing = {t["title"] for t in api.call("GET", f"/units/{offering}/topics") or []}
    for title in unit["topics"]:
        if title not in existing:
            api.call("POST", f"/units/{offering}/topics", {"title": title})
    log(f"  topics: {len(unit['topics'])}")

    # Upload everything first, so the worker can process while we wait.
    for m in unit["materials"]:
        if m["filename"] in s["materials"]:
            continue
        path = download(m["url"], DOWNLOADS / unit["code"] / m["filename"])
        query = urllib.parse.urlencode({"filename": m["filename"]})
        with path.open("rb") as f:
            row = api.call("POST", f"/units/{offering}/materials?{query}", stream=f, size=path.stat().st_size)
        s["materials"][m["filename"]] = row["id"]
        save_state(state)
        log(f"  uploaded {m['filename']}")

    for m in unit["materials"]:
        mid = s["materials"][m["filename"]]
        row = wait_ready(api, offering, mid, m["filename"], timeout_s)
        if row.get("status") == "failed":
            log(f"  ! {m['filename']} failed: {row.get('error')}. Fix the cause, then retry it in the Library or re-run after it's retried.")
            continue
        if not row.get("published"):
            api.call("POST", f"/units/{offering}/materials/{mid}/publish")
            log(f"  published {m['filename']}")

    if not keep_pending:
        approved = 0
        for lecture in api.call("GET", f"/units/{offering}/lectures/review") or []:
            if any(c["status"] == "pending" for c in lecture["clips"]):
                approved += (api.call("POST", f"/units/{offering}/lectures/{lecture['id']}/approve-pending") or {}).get("approved", 0)
        log(f"  approved {approved} proposed clips")

    info = api.call("GET", f"/offerings/{offering}")
    if info["status"] != "published":
        api.call("POST", f"/offerings/{offering}/publish")
    log("  Offering published")


def start_sessions(api_base: str, cookie: str, manifest: dict, state: dict, only: str | None) -> None:
    """Start each unit's demo session as the given browser identity (once per unit)."""
    me = Api(api_base, cookie)
    identity = me.call("GET", "/identity")
    if me.token != cookie:
        raise SystemExit("seed-demo: that cookie isn't a current Athena identity (the API issued a new one). "
                         "Copy athena_session again from the browser you'll demo with.")
    log(f"\n== Demo sessions for your browser ({identity.get('role', 'student')})")
    for unit in manifest["units"]:
        if only and unit["code"] != only:
            continue
        offering = state["units"].get(unit["code"], {}).get("offering_id")
        if not offering:
            log(f"  {unit['code']}: not seeded yet, skipped")
            continue
        existing = {s.get("goal") for s in me.call("GET", f"/units/{offering}/sessions") or []}
        for n, goal in enumerate(unit.get("session_goals", []), 1):
            if goal in existing:
                log(f"  {unit['code']}: “{goal}” already exists")
                continue
            log(f"  {unit['code']}: starting “{goal}” (the tutor plans and asks a first question; ~10–30 s)")
            # The model occasionally returns an unusable plan; a new key retries from scratch.
            for attempt in range(4):
                try:
                    created = me.call("POST", f"/units/{offering}/sessions", {"goal": goal},
                                      headers={"Idempotency-Key": f"demo-session-{unit['code']}-{n}-{attempt}"})
                    break
                except SystemExit as e:
                    log(f"    retrying: {e}")
            else:
                log(f"  ! {unit['code']}: “{goal}” could not be started; re-run to try again")
                continue
            first = (created or {}).get("messages", [{}])[0].get("content", "")
            log(f"    tutor: {first[:140]}")


# --- sample data (Progress and Insights) -----------------------------------------------
# Invented numbers from the manifest's `sample_data`, written straight into the local
# database (there is no API for writing assessment evidence). Every row id starts with
# "sample:", the app labels it as sample data, and --remove-sample-data deletes it.
# Like other aggregate events, sample cohort rows expire with the 30-day retention sweep.

SAMPLE = "sample:"


def _db():
    import sqlite3
    db = sqlite3.connect(Path(os.environ.get("ATHENA_DB", DATA / "athena.db")), timeout=30)
    db.row_factory = sqlite3.Row
    return db


def student_for_cookie(cookie: str) -> str | None:
    """Look up which identity a browser cookie belongs to (local admin read; the cookie isn't stored)."""
    import hashlib
    with _db() as db:
        row = db.execute("SELECT student_id FROM anonymous_identities WHERE token_hash=? AND expires_at>?",
                         (hashlib.sha256(cookie.encode()).hexdigest(), time.time())).fetchone()
    return row[0] if row else None


def _topic_concepts(db, offering: str) -> dict:
    return {r["title"]: r["concept_id"] for r in db.execute("SELECT title, concept_id FROM offering_topics WHERE offering_id=?", (offering,))}


def seed_sample_cohort(unit: dict, state: dict) -> None:
    """A fake class of anonymous Environments, so the lecturer's Insights view has aggregates to show."""
    import random
    offering, sample = state["units"].get(unit["code"], {}).get("offering_id"), unit.get("sample_data")
    if not offering or not sample:
        return
    rng = random.Random(unit["code"])  # Same numbers on every run.
    now = time.time()
    with _db() as db:
        concepts = _topic_concepts(db, offering)
        db.execute("DELETE FROM aggregate_events WHERE offering_id=? AND id LIKE ?", (offering, SAMPLE + "%"))
        rows = []
        for e in range(sample["cohort_environments"]):
            env = f"{SAMPLE}env:{unit['code']}:{e}"
            when = lambda: now - rng.uniform(0, 14 * 86400)  # noqa: E731  (within the last two weeks)
            for s in range(rng.randint(1, 3)):
                session = f"{SAMPLE}session:{unit['code']}:{e}:{s}"
                rows.append((f"start:{session}", env, session, None, "started", "none", when()))
                if rng.random() < .6:
                    rows.append((f"complete:{session}", env, session, None, "complete", "none", when()))
                for title, spec in sample["topics"].items():
                    if title not in concepts or rng.random() < .35:
                        continue
                    for a in range(rng.randint(1, 3)):
                        hard = rng.random() < spec["cohort_difficulty"]
                        outcome = rng.choice(["incorrect", "partial"]) if hard else "correct"
                        category = rng.choice(["needs_practice", "needs_practice", "prerequisite_gap", "needs_independent_reasoning"]) if hard else "none"
                        rows.append((f"{session}:{title}:{a}", env, session, concepts[title], outcome, category, when()))
            for p in range(rng.randint(0, 6)):
                rows.append((f"{SAMPLE}practice:{unit['code']}:{e}:{p}", env, "", None,
                             "practice_correct" if rng.random() < .7 else "practice_incorrect", "none", when()))
        db.executemany("INSERT INTO aggregate_events VALUES (?,?,?,?,?,?,?,?)",
                       [(id if id.startswith(SAMPLE) else SAMPLE + id, offering, *rest) for id, *rest in rows])
    log(f"  {unit['code']}: sample cohort of {sample['cohort_environments']} Environments ({len(rows)} events)")


def seed_sample_profile(student: str, unit: dict, state: dict) -> None:
    """Fake assessment history for one student in one unit, so Progress shows estimates with intervals."""
    import random
    offering, sample = state["units"].get(unit["code"], {}).get("offering_id"), unit.get("sample_data")
    if not offering or not sample:
        return
    rng = random.Random(unit["code"] + student)
    now = time.time()
    created = state.setdefault("sample_profiles", {}).setdefault(student, [])
    with _db() as db:
        concepts = _topic_concepts(db, offering)
        _remove_profile_rows(db, student, offering)
        for title, spec in sample["topics"].items():
            concept = concepts.get(title)
            if not concept:
                continue
            correct, assessed = spec["student"]
            outcomes = ["correct"] * correct + ["incorrect"] * (assessed - correct)
            rng.shuffle(outcomes)
            accuracy = correct / assessed if assessed else 0
            status = "unknown" if not assessed else "mastered" if accuracy >= .85 and assessed >= 8 else "developing"
            note = {"unknown": "Not assessed yet.", "mastered": "Independent checks support mastery.",
                    "developing": "Practise applying this Concept independently."}[status]
            if not db.execute("SELECT 1 FROM learner_concepts WHERE student_id=? AND concept_id=?", (student, concept)).fetchone():
                created.append([offering, concept])
            db.execute("INSERT INTO learner_concepts VALUES (?,?,?,?,?,?) ON CONFLICT(student_id,concept_id) DO UPDATE SET "
                       "status=excluded.status, note=excluded.note, evidence_count=evidence_count+excluded.evidence_count, updated_at=excluded.updated_at",
                       (student, concept, status, note, assessed, now - rng.uniform(0, 3 * 86400)))
            db.execute("INSERT OR IGNORE INTO learner_concept_offerings VALUES (?,?,?)", (student, offering, concept))
            for i, outcome in enumerate(outcomes):
                id = f"{SAMPLE}{student}:{offering}:{concept}:{i}"
                db.execute("INSERT INTO learner_evidence VALUES (?,?,?,?,?,?,?,?,?)",
                           (id, student, offering, SAMPLE + "session", concept, f"{SAMPLE}{i}", outcome, "[]", now - rng.uniform(3, 21) * 86400))
                db.execute("INSERT INTO learner_evidence_state VALUES (?,?,?)", (id, status, note))
    save_state(state)
    log(f"  {unit['code']}: sample Progress for your browser ({sum(1 for t in sample['topics'].values() if t['student'][1])} assessed topics)")


def _remove_profile_rows(db, student: str, offering: str | None) -> None:
    where, args = "student_id=? AND id LIKE ?", [student, SAMPLE + "%"]
    if offering:
        where, args = where + " AND offering_id=?", args + [offering]
    removed = db.execute(f"SELECT concept_id, COUNT(*) FROM learner_evidence WHERE {where} GROUP BY concept_id", args).fetchall()
    db.execute(f"DELETE FROM learner_evidence_state WHERE id IN (SELECT id FROM learner_evidence WHERE {where})", args)
    db.execute(f"DELETE FROM learner_evidence WHERE {where}", args)
    for concept, n in removed:
        db.execute("UPDATE learner_concepts SET evidence_count=MAX(0, evidence_count-?) WHERE student_id=? AND concept_id=?", (n, student, concept))


def remove_sample_data(state: dict) -> None:
    offerings = [u["offering_id"] for u in state["units"].values() if u.get("offering_id")]
    with _db() as db:
        for offering in offerings:
            db.execute("DELETE FROM aggregate_events WHERE offering_id=? AND id LIKE ?", (offering, SAMPLE + "%"))
        for student, rows in state.get("sample_profiles", {}).items():
            _remove_profile_rows(db, student, None)
            for offering, concept in rows:  # Rows that only exist because of the sample data.
                if not db.execute("SELECT 1 FROM learner_evidence WHERE student_id=? AND concept_id=?", (student, concept)).fetchone() and \
                   not db.execute("SELECT 1 FROM session_concepts WHERE student_id=? AND concept_id=?", (student, concept)).fetchone():
                    db.execute("DELETE FROM learner_concepts WHERE student_id=? AND concept_id=?", (student, concept))
                    db.execute("DELETE FROM learner_concept_offerings WHERE student_id=? AND offering_id=? AND concept_id=?", (student, offering, concept))
    state.pop("sample_profiles", None)
    save_state(state)
    log("Sample data removed.")


def main() -> None:
    p = argparse.ArgumentParser(description="Seed the chemistry, physics and coding demo units.")
    p.add_argument("--api", default=os.environ.get("ATHENA_API_URL", "http://127.0.0.1:8000"))
    p.add_argument("--keep-pending", action="store_true", help="leave proposed clips for a lecturer to review live")
    p.add_argument("--only", help="seed one unit code, e.g. CHEM1001")
    p.add_argument("--timeout-min", type=int, default=90, help="max wait per material (default 90)")
    p.add_argument("--sessions-for-cookie", metavar="COOKIE", default=os.environ.get("ATHENA_DEMO_COOKIE"),
                   help="your browser's athena_session cookie: start each unit's demo session for you")
    p.add_argument("--sessions-only", action="store_true", help="only start the demo sessions (units already seeded)")
    p.add_argument("--sample-data", action="store_true",
                   help="add invented, labelled sample data: a class cohort for Insights and (with the cookie) your Progress")
    p.add_argument("--remove-sample-data", action="store_true", help="delete all seeded sample data and exit")
    args = p.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    state = load_state()
    if args.remove_sample_data:
        return remove_sample_data(state)
    api = Api(args.api, state.get("lecturer_cookie"))
    api.call("GET", "/health")
    if args.sample_data:
        student = student_for_cookie(args.sessions_for_cookie.strip()) if args.sessions_for_cookie else None
        if args.sessions_for_cookie and not student:
            raise SystemExit("seed-demo: that cookie isn't a current Athena identity. Copy athena_session again.")
        log("\n== Sample data (labelled “sample data” in the app)")
        for unit in manifest["units"]:
            if args.only and unit["code"] != args.only:
                continue
            seed_sample_cohort(unit, state)
            if student:
                seed_sample_profile(student, unit, state)
        if not args.sessions_for_cookie:
            log("  (pass --sessions-for-cookie to also add sample Progress for your browser)")
        return
    if not args.sessions_only:
        become_lecturer(api, state)
        for unit in manifest["units"]:
            if args.only and unit["code"] != args.only:
                continue
            seed_unit(api, unit, state, keep_pending=args.keep_pending, timeout_s=args.timeout_min * 60)
    if args.sessions_for_cookie:
        start_sessions(args.api, args.sessions_for_cookie.strip(), manifest, state, args.only)
    elif args.sessions_only:
        raise SystemExit("seed-demo: --sessions-only needs --sessions-for-cookie (or ATHENA_DEMO_COOKIE).")

    log(f"\nDone. Demo lecturer cookie and Offering ids: {STATE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
