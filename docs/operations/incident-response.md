# Incident Response

1. Identify affected tenant, request IDs, release digest and time window without copying raw SQL.
2. For credential exposure, revoke first, rotate dependants, then investigate audit history.
3. For unsafe-query reports, disable the source, preserve audit logs and verify its role was read-only.
4. For quality regression, pin the last accepted model/prompt and run the offline baseline.
5. For database pressure, stop query traffic before scaling pools; pool growth can amplify outages.
6. Record scope, impact, containment, root cause and corrective tests in the postmortem.
