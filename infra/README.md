# Local deployment

The first version uses SQLite and local files, not Postgres/Redis/MinIO.
See [single-host operations](../docs/operations.md) for persistent volumes, worker
isolation, startup, configuration and backup/restore. Run `npm run dev:all` from
the root after `bash scripts/setup.sh`. The private Python worker launches bounded
containers; there is no public worker or agent API.
