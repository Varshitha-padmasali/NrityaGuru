import asyncio
import logging

from starlette.responses import JSONResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import feedback, health, knowledge, practice, sequences, tutor
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.seed import DEFAULT_ASSETS_DIR

logger = logging.getLogger(__name__)
MAX_UPLOAD_REQUEST_BYTES = 101 * 1024 * 1024


class PracticeUploadSizeLimit:
    """Reject oversized multipart bodies before Starlette spools file parts to disk."""

    def __init__(self, app, max_request_bytes: int = MAX_UPLOAD_REQUEST_BYTES, upload_limit_mb: int = 100):
        self.app = app
        self.max_request_bytes = max_request_bytes
        self.upload_limit_mb = upload_limit_mb
        self._active_uploads = asyncio.Semaphore(2)

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope.get("type") != "http" or scope.get("method") != "POST" or not (
            path.startswith("/api/practice/sessions/") and path.endswith("/video")
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_length = headers.get(b"content-length")
        if raw_length:
            try:
                if int(raw_length) > self.max_request_bytes:
                    await JSONResponse(
                        status_code=413,
                        content={"detail": {"code": "upload_size_limit", "message": f"Video uploads are limited to {self.upload_limit_mb} MB."}},
                    )(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})(scope, receive, send)
                return

        if self._active_uploads.locked():
            await JSONResponse(
                status_code=429,
                headers={"Retry-After": "5"},
                content={"detail": {"code": "upload_capacity", "message": "Another practice video is being processed. Retry shortly."}},
            )(scope, receive, send)
            return
        await self._active_uploads.acquire()

        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            if message.get("type") == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_request_bytes:
                    raise OverflowError("practice upload exceeded request size limit")
            return message

        try:
            await self.app(scope, limited_receive, send)
        except OverflowError:
            await JSONResponse(
                status_code=413,
                content={"detail": {"code": "upload_size_limit", "message": f"Video uploads are limited to {self.upload_limit_mb} MB."}},
            )(scope, receive, send)
        finally:
            self._active_uploads.release()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.mount("/static", StaticFiles(directory=DEFAULT_ASSETS_DIR), name="static-assets")
    app.add_middleware(
        PracticeUploadSizeLimit,
        max_request_bytes=settings.max_video_upload_mb * 1024 * 1024 + 1024 * 1024,
        upload_limit_mb=settings.max_video_upload_mb,
    )
    register_exception_handlers(app)

    origins = settings.cors_origins_list
    if origins:
        # No credentials/cookies are used, so no allow_credentials. Only the methods we expose.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Reference-Review-Token"],
        )

    app.include_router(health.router)
    app.include_router(knowledge.router)
    app.include_router(sequences.router)
    app.include_router(tutor.router)
    app.include_router(feedback.router)
    app.include_router(practice.router)

    logger.info("Started %s (env=%s)", settings.app_name, settings.app_env)
    return app


app = create_app()
