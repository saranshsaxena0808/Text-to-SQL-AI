from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response


HTTP_REQUESTS = Counter(
    "text2sql_http_requests_total", "HTTP requests", ("method", "route", "status"))
HTTP_DURATION = Histogram(
    "text2sql_http_request_duration_seconds", "HTTP request latency", ("method", "route"))


def observe_request(method: str, route: str, status: int, duration_seconds: float) -> None:
    HTTP_REQUESTS.labels(method, route, str(status)).inc()
    HTTP_DURATION.labels(method, route).observe(duration_seconds)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
