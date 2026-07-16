import type { ApiErrorBody, DataSource, QueryHistoryItem, QueryResponse } from "./types";

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
  }
}

export interface ApiClient {
  listDataSources(): Promise<DataSource[]>;
  runQuery(input: { data_source_id: string; question: string; model: string }): Promise<QueryResponse>;
  executeEdited(queryRunId: string, sql: string): Promise<QueryResponse>;
  history(limit?: number, offset?: number): Promise<{ items: QueryHistoryItem[]; limit: number; offset: number }>;
}

interface ClientConfig { baseUrl: string; tenantId: string; userId: string }

export function createApiClient(config: ClientConfig): ApiClient {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${config.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Tenant-ID": config.tenantId,
        "X-User-ID": config.userId,
        ...init?.headers,
      },
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new ApiError(response.status, payload.error ?? {
        code: "HTTP_ERROR", message: "Request failed", details: null,
        request_id: response.headers.get("X-Request-ID") ?? "unknown",
      });
    }
    return payload as T;
  }

  return {
    listDataSources: () => request<DataSource[]>("/data-sources"),
    runQuery: (input) => request<QueryResponse>("/queries", {
      method: "POST", body: JSON.stringify(input),
    }),
    executeEdited: (queryRunId, sql) => request<QueryResponse>(`/queries/${queryRunId}/execute`, {
      method: "POST", body: JSON.stringify({ sql }),
    }),
    history: (limit = 50, offset = 0) => request(`/queries?limit=${limit}&offset=${offset}`),
  };
}
