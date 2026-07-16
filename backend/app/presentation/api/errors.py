from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    DataSourceNotFoundError, ExecutionConnectionError, ExecutionDatabaseError,
    ExecutionQueryError, ExecutionRejectedError, ExecutionTimeoutError,
    LLMConfigurationError, LLMRateLimitError, LLMResponseError, LLMServiceUnavailableError,
    RepositoryError,
)
from app.infrastructure.observability import get_logger


logger = get_logger(__name__)


def _response(request: Request, status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "details": details,
        "request_id": getattr(request.state, "request_id", "unknown"),
    }})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"location": list(item["loc"]), "message": item["msg"],
                    "type": item["type"]} for item in exc.errors()]
        return _response(request, 422, "REQUEST_VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = {401: "UNAUTHORIZED", 404: "RESOURCE_NOT_FOUND",
                503: "NOT_READY"}.get(exc.status_code, "HTTP_ERROR")
        return _response(request, exc.status_code, code, str(exc.detail))

    mappings = {
        DataSourceNotFoundError: (404, "RESOURCE_NOT_FOUND", "Requested resource was not found"),
        ExecutionRejectedError: (400, "SQL_REJECTED", "SQL was not approved for execution"),
        ExecutionQueryError: (400, "SQL_EXECUTION_ERROR", "Database rejected the SQL query"),
        ExecutionTimeoutError: (504, "SQL_TIMEOUT", "SQL execution timed out"),
        ExecutionConnectionError: (503, "DATABASE_UNAVAILABLE", "Target database is unavailable"),
        ExecutionDatabaseError: (502, "DATABASE_ERROR", "Target database execution failed"),
        LLMRateLimitError: (429, "LLM_RATE_LIMITED", "Model provider rate limit exceeded"),
        LLMConfigurationError: (503, "LLM_CONFIGURATION_ERROR", "Model provider is not configured"),
        LLMResponseError: (502, "LLM_INVALID_RESPONSE", "Model provider returned an invalid response"),
        LLMServiceUnavailableError: (503, "LLM_UNAVAILABLE", "Model provider is unavailable"),
        RepositoryError: (503, "PERSISTENCE_ERROR", "Application persistence is unavailable"),
    }
    for exception_type, (status, code, message) in mappings.items():
        async def handler(request: Request, exc: Exception, _status=status, _code=code, _message=message):
            return _response(request, _status, _code, _message)
        app.add_exception_handler(exception_type, handler)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled API exception", extra={
            "event": "api_unhandled_error", "request_id": getattr(request.state, "request_id", None)
        })
        return _response(request, 500, "INTERNAL_ERROR", "An unexpected error occurred")
