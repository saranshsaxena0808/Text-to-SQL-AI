import unittest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from app.config.settings import AuthSettings
from app.presentation.api.authentication import (
    OidcIdentityProvider, TrustedHeaderIdentityProvider, build_identity_provider,
)


class Request:
    def __init__(self, headers):
        self.headers = headers


class FakeJwks:
    def __init__(self, url, cache_keys):
        self.url = url

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key="public-key")


class FakeJwt:
    PyJWKClient = FakeJwks

    def __init__(self, claims):
        self.claims = claims
        self.calls = []

    def decode(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.claims


class AuthenticationTests(unittest.TestCase):
    def test_trusted_headers_parse_identity(self):
        tenant, user = uuid4(), uuid4()
        identity = TrustedHeaderIdentityProvider().authenticate(Request({
            "X-Tenant-ID": str(tenant), "X-User-ID": str(user)}))
        self.assertEqual((identity.tenant_id, identity.user_id), (tenant, user))

    def test_production_rejects_trusted_header_mode(self):
        with self.assertRaisesRegex(ValueError, "Production requires"):
            build_identity_provider(AuthSettings(mode="trusted_headers"), "production")

    def test_oidc_validates_and_maps_configured_claims(self):
        tenant, user = uuid4(), uuid4()
        fake = FakeJwt({"tenant_id": str(tenant), "sub": str(user), "exp": 1, "iat": 1})
        settings = AuthSettings(mode="oidc", issuer="https://issuer/", audience="api",
                                jwks_url="https://issuer/jwks")
        identity = OidcIdentityProvider(settings, fake).authenticate(
            Request({"Authorization": "Bearer signed-token"}))
        self.assertEqual((identity.tenant_id, identity.user_id), (tenant, user))
        self.assertEqual(fake.calls[0][1]["issuer"], "https://issuer/")
        self.assertEqual(fake.calls[0][1]["audience"], "api")

    def test_oidc_rejects_missing_token_and_symmetric_algorithms(self):
        base = dict(mode="oidc", issuer="https://issuer/", audience="api",
                    jwks_url="https://issuer/jwks")
        with self.assertRaises(ValueError):
            OidcIdentityProvider(AuthSettings(**base, algorithms=["HS256"]), FakeJwt({}))
        provider = OidcIdentityProvider(AuthSettings(**base), FakeJwt({}))
        with self.assertRaises(HTTPException) as caught:
            provider.authenticate(Request({}))
        self.assertEqual(caught.exception.status_code, 401)
