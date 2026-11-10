"""athena-srs: manage SRS question banks.

  athena-srs load-starter            load the built-in CSE5ALG and CSE5DMI banks
  athena-srs load <bank.json>        load a bank from a JSON file
  athena-srs export-starter <dir>    write the built-in banks as JSON (to read or edit)
  athena-srs generate --clips <clips.json> --topics <topics.json> [--per-clip 2]
                                     draft pending items from an indexed lecture (needs OpenAI)

Loading replaces a unit's bank; students' cards and history are kept.
"""

import argparse
import os
from pathlib import Path

from .models import Bank
from .starter_banks import starter_banks
from .store import SqliteStore


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="athena-srs", description="Manage SRS question banks.")
    p.add_argument("--db", type=Path, default=Path(os.environ.get("ATHENA_DB", "data/athena.db")))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load-starter", help="load the built-in banks")
    load = sub.add_parser("load", help="load a bank JSON file")
    load.add_argument("file", type=Path)
    export = sub.add_parser("export-starter", help="write the built-in banks as JSON")
    export.add_argument("dir", type=Path)
    gen = sub.add_parser("generate", help="draft pending items from an indexed lecture's clips.json")
    gen.add_argument("--clips", type=Path, required=True, help="workers/indexer/data/<recording>/clips.json")
    gen.add_argument("--topics", type=Path, required=True, help="topics JSON, e.g. workers/indexer/topics/cse5alg.json")
    gen.add_argument("--offering", help="offering id (default: from clips.json)")
    gen.add_argument("--per-clip", type=int, default=2)
    gen.add_argument("--max-clips", type=int, default=20)
    gen.add_argument("--model", help="OpenAI model id (default: OPENAI_MODEL)")
    args = p.parse_args(argv)

    if args.cmd == "generate":
        return _generate(args)

    if args.cmd == "export-starter":
        args.dir.mkdir(parents=True, exist_ok=True)
        for bank in starter_banks():
            path = args.dir / f"{bank.offering_id}.json"
            path.write_text(bank.model_dump_json(indent=2))
            print(f"wrote {path}")
        return

    banks = starter_banks() if args.cmd == "load-starter" else [Bank.model_validate_json(args.file.read_text())]
    store = SqliteStore(args.db)
    for bank in banks:
        store.put_bank(bank)
        variants = sum(len(i.variants) for i in bank.items)
        print(f"{bank.offering_id}: {len(bank.items)} items, {variants} wordings → {args.db}")
    store.close()


if __name__ == "__main__":
    main()


def _generate(args) -> None:
    import json

    from ..env import load_dotenv
    from .generate import GenerateError, OpenAIDraftModel, generate, merge_into, sources_from_clips_json

    load_dotenv()
    offering, sources = sources_from_clips_json(args.clips)
    offering = args.offering or offering
    if not offering:
        raise SystemExit("athena-srs: no offering id in clips.json; pass --offering")
    topics = json.loads(args.topics.read_text())["topics"]
    sources = sources[: args.max_clips]
    store = SqliteStore(args.db)
    current = store.get_bank(offering)
    try:
        report = generate(
            sources, topics, offering, OpenAIDraftModel(args.model), per_source=args.per_clip,
            existing=list(current.items) if current else [],
            on_progress=lambda n, total, s: print(f"clip {n}/{total}: {s.title}", flush=True),
        )
    except GenerateError as e:
        raise SystemExit(f"athena-srs: {e}") from None

    store.put_bank(merge_into(store.get_bank(offering), offering, report.accepted))
    store.close()
    print(f"\n{len(report.accepted)} items drafted (pending lecturer approval), {len(report.rejected)} rejected by checks")
    for concept, problems in report.rejected:
        print(f"  rejected: {concept}: {'; '.join(problems)}")
