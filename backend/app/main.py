from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.pins import router as pins_router
from app.api.providers import router as providers_router
from app.api.results import router as results_router
from app.api.schema import router as schema_router
from app.config import get_settings
from app.influx.client import InfluxClient
from app.llm.registry import ProviderRegistry
from app.state.db import init_schema, make_engine
from app.state.refresh import SchemaRefresher
from app.state.results import ResultCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    engine = make_engine(settings)
    init_schema(engine)
    app.state.db_engine = engine

    influx = InfluxClient(settings)
    app.state.influx = influx

    refresher = SchemaRefresher(engine=engine, influx=influx)
    app.state.refresher = refresher
    refresher.start()

    app.state.results = ResultCache(ttl_seconds=settings.results_ttl_seconds)

    registry = ProviderRegistry(settings)
    app.state.registry = registry
    # Default LLM kept for legacy code paths (health endpoint, etc.) — chat
    # routes resolve per-request through the registry.
    try:
        app.state.llm = registry.get(settings.llm_provider)
        logger.info("default LLM: %s (%s)", app.state.llm.name, app.state.llm.model)
    except Exception as exc:
        app.state.llm = None
        logger.warning("default LLM unavailable: %s", exc)

    logger.info(
        "Started — InfluxDB target %s:%s/%s, LLM %s, state DB %s",
        settings.influx_host,
        settings.influx_port,
        settings.influx_database,
        settings.llm_provider,
        settings.state_db_path,
    )
    try:
        yield
    finally:
        await refresher.stop()
        influx.close()


def create_app() -> FastAPI:
    app = FastAPI(title="HouseDataBrowser", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(schema_router)
    app.include_router(chat_router)
    app.include_router(results_router)
    app.include_router(pins_router)
    app.include_router(providers_router)

    static_dir = Path(__file__).resolve().parents[1] / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
