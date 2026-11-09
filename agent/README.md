# Athena Agent

Independent Python backend for Athena's adaptive learning agent. Product requirements are in [AGENTS.md](../AGENTS.md); incremental tasks are in [MODULES.md](../MODULES.md).

## Setup

Install Python 3.12 or newer and uv. Run these commands from `agent/`:

```sh
uv sync
```

This creates a local `.venv`, installs the agent package in editable mode, and installs development dependencies from `uv.lock`.

## Test

```sh
uv run pytest
```

The initial smoke test verifies that the installed `athena_agent` package can be imported. No frontend, retrieval service, model credentials, or other running services are required. Initial dependency installation requires access to a Python package registry.

## Build

```sh
uv build
```

The source distribution and wheel are written to `dist/`.

## Project layout

- `src/athena_agent/`: agent package.
- `tests/`: automated tests.
- `pyproject.toml`: package, development dependency, and test configuration.
- `uv.lock`: resolved dependencies for reproducible setup.

Step 01.1 establishes packaging and testing only. Learning schemas, LLM integration, and service APIs are added in later steps. Keep agent dependencies and configuration within this directory, separate from other application components.
