# Security Operations

- Terminate TLS at ingress and expose the backend only to ingress and monitoring networks.
- Validate OIDC issuer, audience, signature, expiration and tenant/user claims.
- Rotate credentials; revoke the previously exposed-looking Groq example key.
- Use read-only target roles. Application guardrails and database permissions are independent layers.
- Restrict `/metrics`; its labels exclude tenants, questions and SQL.
- Alert on auth failures, blocked-query spikes, readiness, latency, errors and pool exhaustion.
- Run dependency and image scans each release; resolve critical/high findings before deployment.
