"""Minimal .env loading (same rules as workers/indexer): nearest .env upward; real env vars win."""

import os
from pathlib import Path


def load_dotenv(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for folder in [here, *here.parents]:
        path = folder / ".env"
        if path.is_file():
            for raw in path.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key, value = key.strip().removeprefix("export ").strip(), value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                os.environ.setdefault(key, value)
            return path
    return None
