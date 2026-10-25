"""Central, safe error responses. Never include stack traces, SQL or connection strings."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.enums import EvaluationErrorCode
from app.db.database import DatabaseNotConfiguredError
from app.repositories.errors import PersistenceError
from app.services.evaluation_errors import EvaluationValidationError
from app.services.text_processing import InputValidationError

logger = logging.getLogger(__name__)

EVALUATION_ERROR_STATUS = {
    EvaluationErrorCode.INVALID_SESSION_ID: 422,
    EvaluationErrorCode.SESSION_NOT_FOUND: 404,
    EvaluationErrorCode.SESSION_MISMATCH: 502,
    EvaluationErrorCode.MALFORMED_RESULT: 422,
    EvaluationErrorCode.UNSUPPORTED_VERSION: 422,
    EvaluationErrorCode.UNKNOWN_REFERENCE: 422,
    EvaluationErrorCode.MOCK_DATA_IN_REAL_STORE: 500,
    EvaluationErrorCode.STORE_UNAVAILABLE: 503,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InputValidationError)
    async def _invalid_input(_: Request, exc: InputValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(EvaluationValidationError)
    async def _evaluation_error(_: Request, exc: EvaluationValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=EVALUATION_ERROR_STATUS.get(exc.code, 500),
            content={"detail": exc.message, "code": exc.code.value},
        )

    @app.exception_handler(PersistenceError)
    async def _persistence_error(_: Request, __: PersistenceError) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "The result store is temporarily unavailable."}
        )

    @app.exception_handler(DatabaseNotConfiguredError)
    async def _db_not_configured(_: Request, __: DatabaseNotConfiguredError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "The database is not configured."})

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Log only the exception type: the message can contain connection details.
        logger.error("Database error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503, content={"detail": "The knowledge base is temporarily unavailable."}
        )
