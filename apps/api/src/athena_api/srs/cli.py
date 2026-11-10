"""athena-srs: manage SRS question banks.

  athena-srs load-starter            load the built-in CSE5ALG and CSE5DMI banks
  athena-srs load <bank.json>        load a bank from a JSON file
  athena-srs export-starter <dir>    write the built-in banks as JSON (to read or edit)

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
    args = p.parse_args(argv)

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
