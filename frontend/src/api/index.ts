import { createApiClient } from "./client";

export const api = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1",
  tenantId: import.meta.env.VITE_TENANT_ID ?? "",
  userId: import.meta.env.VITE_USER_ID ?? "",
});

export type { ApiClient } from "./client";
