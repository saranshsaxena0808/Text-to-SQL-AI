from uuid import uuid4
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.infrastructure.observability import get_logger
from app.infrastructure.observability.metrics import observe_request


logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied[:128] if supplied and supplied.isascii() else str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        elapsed = time.perf_counter() - started
        observe_request(request.method, route, response.status_code, elapsed)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        logger.info("HTTP request completed", extra={
            "event": "http_request_completed", "request_id": request_id,
            "method": request.method, "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": elapsed * 1000,
        })
        return response
