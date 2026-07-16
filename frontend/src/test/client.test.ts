import { createApiClient } from "../api/client";

describe("API client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("adds identity headers and parses successful responses", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(
      JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = createApiClient({ baseUrl: "/api/v1", tenantId: "tenant", userId: "user" });
    await client.listDataSources();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({ "X-Tenant-ID": "tenant", "X-User-ID": "user" });
  });

  it("normalizes the backend error envelope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: {
      code: "SQL_REJECTED", message: "SQL was blocked", details: null, request_id: "req-1",
    }}), { status: 400, headers: { "Content-Type": "application/json" } }));
    const client = createApiClient({ baseUrl: "/api/v1", tenantId: "tenant", userId: "user" });
    await expect(client.runQuery({ data_source_id: "id", question: "q", model: "m" }))
      .rejects.toEqual(expect.objectContaining({ status: 400, message: "SQL was blocked" }));
  });
});
