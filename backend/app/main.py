import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import feedback, health, knowledge, tutor
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    register_exception_handlers(app)

    origins = settings.cors_origins_list
    if origins:
        # No credentials/cookies are used, so no allow_credentials. Only the methods we expose.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    app.include_router(health.router)
    app.include_router(knowledge.router)
    app.include_router(tutor.router)
    app.include_router(feedback.router)

    logger.info("Started %s (env=%s)", settings.app_name, settings.app_env)
    return app


app = create_app()
