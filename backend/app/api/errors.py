"""Exception handlers: clients get `{code, message}`; tracebacks stay in the server log."""

from __future__ import annotations

import errno
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ConflictError, DatabaseError, DiskFullError, ErrorCode

logger = logging.getLogger(__name__)

_HTTP_CODES: dict[int, ErrorCode] = {
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.FILE_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_FORMAT,
}


def _error(status: int, code: ErrorCode | str, message: str, **extra: object) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": str(code), "message": message, **extra}}
    )


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    log = logger.error if exc.status_code >= 500 else logger.info
    log("app_error", extra={"code": exc.code.value, "path": request.url.path})
    return JSONResponse(status_code=exc.status_code, content={"error": exc.to_payload()})


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [
        {"loc": [str(part) for part in err.get("loc", ())], "msg": err.get("msg", "")} for err in exc.errors()
    ]
    return _error(422, ErrorCode.VALIDATION_ERROR, "Request validation failed.", fields=fields)


async def _model_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Pydantic errors raised inside services (e.g. a built request failing a guard) are client errors."""
    assert isinstance(exc, ValidationError)
    fields = [
        {"loc": [str(p) for p in err.get("loc", ())], "msg": err.get("msg", "")} for err in exc.errors()
    ]
    return _error(422, ErrorCode.VALIDATION_ERROR, "Request validation failed.", fields=fields)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _error(exc.status_code, code, message)


async def _db_error(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, IntegrityError):
        logger.info("integrity_error", extra={"path": request.url.path, "detail": str(exc.orig)})
        return await _app_error(request, ConflictError("The change violates a data constraint."))
    logger.exception("database_error", extra={"path": request.url.path})
    return await _app_error(request, DatabaseError())


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return await _app_error(request, DiskFullError())
    logger.exception("unhandled_error", extra={"path": request.url.path})
    return _error(500, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(ValidationError, _model_validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(SQLAlchemyError, _db_error)
    app.add_exception_handler(Exception, _unhandled_error)
