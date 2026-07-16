from fastapi import Request

from app.bootstrap.container import ApplicationContainer


from app.presentation.api.authentication import Identity


def get_container(request: Request) -> ApplicationContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("Application container is not initialized")
    return container


def get_identity(request: Request) -> Identity:
    return request.app.state.identity_provider.authenticate(request)
