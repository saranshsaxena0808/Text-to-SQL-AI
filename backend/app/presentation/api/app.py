from contextlib import asynccontextmanager
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap.container import ApplicationContainer
from app.presentation.api.errors import register_exception_handlers
from app.presentation.api.middleware import RequestContextMiddleware
from app.presentation.api.authentication import IdentityProvider, TrustedHeaderIdentityProvider
from app.infrastructure.observability.metrics import metrics_response
from app.presentation.api.routes import router


def create_app(container: ApplicationContainer | None = None,
               container_factory: Callable[[], ApplicationContainer] | None = None,
               allowed_origins: list[str] | None = None,
               identity_provider: IdentityProvider | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if container is not None:
            app.state.container = container
        elif container_factory is not None:
            app.state.container = container_factory()
        else:
            raise RuntimeError("Application container factory is required")
        try:
            yield
        finally:
            app.state.container.shutdown()

    app = FastAPI(title="Text2SQL AI API", version="1.0.0", lifespan=lifespan)
    app.state.identity_provider = identity_provider or TrustedHeaderIdentityProvider()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-User-ID", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(router)
    app.add_api_route("/metrics", metrics_response, methods=["GET"], include_in_schema=False)
    return app
