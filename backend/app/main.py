"""FastAPI application factory.

Phase 1 provides: configuration, structured logging, error envelope, request
correlation, CORS, health/readiness, the module registry and the versioned API
surface. No analytical route serves data yet — intentionally.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.health import router as health_router
from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.db.session import dispose_engine

logger = get_logger(__name__)

API_DESCRIPTION = """
Global fire intelligence API built on NASA FIRMS active-fire observations.

**Status:** Phase 1 (Foundation). Routes are published as soon as their contract
is fixed, but analytical endpoints return `501 not_implemented` until the phase
that builds them. The API never returns invented observations or statistics.

Satellite detections are thermal anomalies. They are not confirmed wildfires and
must not be used as the sole basis for protecting life or property.
"""

TAGS_METADATA = [
    {"name": "system", "description": "Application status, module registry, sources."},
    {"name": "health", "description": "Liveness and readiness probes."},
    {"name": "dashboard", "description": "Global overview aggregates."},
    {"name": "fires", "description": "Fire observation search and map feeds."},
    {"name": "calendar", "description": "Historical burning activity aggregation."},
    {"name": "harmonization", "description": "MODIS–VIIRS association and events."},
    {"name": "anomalies", "description": "Statistical anomaly detection."},
    {"name": "regions", "description": "Regional intelligence."},
    {"name": "exposure", "description": "Geographic exposure screening."},
    {"name": "reports", "description": "Report generation and export."},
    {"name": "assistant", "description": "Tool-calling analytical assistant."},
    {"name": "admin", "description": "Ingestion administration and audit."},
    {"name": "auth", "description": "Authentication and sessions."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "startup",
        environment=settings.environment,
        database_dialect=settings.database_dialect,
        firms_configured=settings.firms_configured,
    )
    if not settings.firms_configured:
        logger.warning(
            "firms_unconfigured",
            detail="FIRMS_MAP_KEY is not set; NASA ingestion cannot run.",
        )
    yield
    dispose_engine()
    logger.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    app = FastAPI(
        title=f"{settings.app_name} API",
        description=API_DESCRIPTION,
        version=settings.app_version,
        openapi_tags=TAGS_METADATA,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Map payloads and calendar/monthly responses compress well and are requested
    # repeatedly; gzip keeps the browser and the loopback link cheap.
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
    if settings.rate_limit_per_minute > 0:
        app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_per_minute)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
