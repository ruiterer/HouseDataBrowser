from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.config import get_settings
from app.influx.client import InfluxClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.influx = InfluxClient(settings)
    logger.info(
        "Started — InfluxDB target %s:%s/%s, LLM provider %s",
        settings.influx_host,
        settings.influx_port,
        settings.influx_database,
        settings.llm_provider,
    )
    try:
        yield
    finally:
        app.state.influx.close()


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

    static_dir = Path(__file__).resolve().parents[1] / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
