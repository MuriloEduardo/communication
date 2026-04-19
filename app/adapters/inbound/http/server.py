from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI

from app.container import Container

logger = structlog.get_logger(__name__)


def create_app(container: Container | None = None) -> FastAPI:
    _container = container or Container()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = _container
        logger.info("http.startup")
        yield
        await _container.shutdown()
        logger.info("http.shutdown")

    app = FastAPI(
        title="Communication Service",
        lifespan=lifespan,
    )

    app.get("/health")(health)

    return app


async def health() -> dict:
    return {"status": "ok"}
