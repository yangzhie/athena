# workers

Python background jobs. Each worker is its own uv package.

- [`indexer/`](indexer/): lecture indexing (recording → transcript → topic-labelled clips). In progress.

Planned: document ingestion (parse, chunk, embed), mastery updates from events.
A Redis queue (Celery or RQ) comes later; workers start as command-line tools.
