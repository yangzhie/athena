"""athena-lectures: import lectures indexed by workers/indexer.

  athena-lectures import <clips.json> [--offering <id>]

Re-importing a re-indexed lecture keeps the review of unchanged clips.
"""

import argparse
import json
import os
from pathlib import Path

from .service import Invalid, LectureService
from .store import SqliteLectureStore


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="athena-lectures")
    p.add_argument("--db", type=Path, default=Path(os.environ.get("ATHENA_DB", "data/athena.db")))
    sub = p.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="import an indexer clips.json")
    imp.add_argument("file", type=Path)
    imp.add_argument("--offering", help="offering id (default: from clips.json)")
    args = p.parse_args(argv)

    store = SqliteLectureStore(args.db)
    try:
        lecture = LectureService(store).import_indexer_file(json.loads(args.file.read_text()), args.offering)
    except Invalid as e:
        raise SystemExit(f"athena-lectures: {e}") from None
    finally:
        store.close()
    pending = sum(1 for c in lecture.clips if c.status == "pending")
    print(f"{lecture.offering_id}: “{lecture.title}”, {len(lecture.clips)} clips ({pending} pending review) → {args.db}")


if __name__ == "__main__":
    main()
