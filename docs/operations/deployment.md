# Deployment Runbook

## Preconditions

- PostgreSQL 17-compatible control database with encrypted storage and backups.
- OIDC issuer, audience and JWKS endpoint. Production refuses trusted identity headers.
- Groq key and database password supplied by the deployment secret manager, never an image or Git.
- Every target data source uses a separate PostgreSQL role with `CONNECT`, `USAGE` and `SELECT` only.

## Release

1. Pin and scan the release commit and both container image digests.
2. Run backend/frontend quality gates and the live PostgreSQL integration job.
3. Run `alembic upgrade head` as a one-shot job before rolling out the API.
4. Deploy backend, verify liveness, readiness and `/metrics` internally.
5. Deploy frontend and perform authenticated query, edited-query and history smoke tests.
6. Run `python backend/scripts/load_test.py <internal-live-url>`.

Compose is a reproducible single-host reference, not an HA orchestrator. Supply all required variables
from a non-committed environment file before `docker compose up --build`.

## Rollback

Roll images back by immutable digest. Migrations are forward-only after traffic reaches a schema; deploy
a corrective migration instead of downgrading. Preserve audit/history according to retention policy.
