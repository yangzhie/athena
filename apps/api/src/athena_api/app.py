"""FastAPI application factory. Modules (SRS first) add their routers here."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Athena API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
