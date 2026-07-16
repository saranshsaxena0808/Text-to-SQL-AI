from app.bootstrap.production import build_production_container
from app.presentation.api import create_app
from app.config import get_settings
from app.presentation.api.authentication import build_identity_provider

settings = get_settings()
app = create_app(container_factory=build_production_container,
                 allowed_origins=settings.api.allowed_origins,
                 identity_provider=build_identity_provider(settings.auth, settings.environment))
