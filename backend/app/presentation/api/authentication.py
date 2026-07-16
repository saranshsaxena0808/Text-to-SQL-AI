from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from fastapi import HTTPException, Request

from app.config.settings import AuthSettings


@dataclass(frozen=True, slots=True)
class Identity:
    tenant_id: UUID
    user_id: UUID


class IdentityProvider(Protocol):
    def authenticate(self, request: Request) -> Identity: ...


class TrustedHeaderIdentityProvider:
    """Identity adapter for local development behind no public ingress."""

    def authenticate(self, request: Request) -> Identity:
        tenant = request.headers.get("X-Tenant-ID")
        user = request.headers.get("X-User-ID")
        if not tenant or not user:
            raise HTTPException(status_code=401, detail="Identity headers are required")
        try:
            return Identity(UUID(tenant), UUID(user))
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid identity headers") from exc


class OidcIdentityProvider:
    """Validates bearer JWTs against an OIDC provider's cached JWKS."""

    def __init__(self, settings: AuthSettings, jwt_module: Any | None = None) -> None:
        if not settings.issuer or not settings.audience or not settings.jwks_url:
            raise ValueError("OIDC issuer, audience and JWKS URL are required")
        if any(value.startswith("HS") or value == "none" for value in settings.algorithms):
            raise ValueError("Only asymmetric OIDC signing algorithms are allowed")
        if jwt_module is None:
            import jwt as jwt_module  # type: ignore[no-redef]
        self._jwt = jwt_module
        self._jwks = jwt_module.PyJWKClient(settings.jwks_url, cache_keys=True)
        self._settings = settings

    def authenticate(self, request: Request) -> Identity:
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Bearer token is required")
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims = self._jwt.decode(
                token, key, algorithms=self._settings.algorithms,
                audience=self._settings.audience, issuer=self._settings.issuer,
                options={"require": ["exp", "iat", self._settings.user_claim,
                                     self._settings.tenant_claim]},
            )
            return Identity(UUID(str(claims[self._settings.tenant_claim])),
                            UUID(str(claims[self._settings.user_claim])))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid bearer token") from exc


def build_identity_provider(settings: AuthSettings, environment: str) -> IdentityProvider:
    if settings.mode == "oidc":
        return OidcIdentityProvider(settings)
    if settings.mode == "trusted_headers" and environment.lower() in {"development", "test"}:
        return TrustedHeaderIdentityProvider()
    raise ValueError("Production requires TEXT2SQL_AUTH__MODE=oidc")
