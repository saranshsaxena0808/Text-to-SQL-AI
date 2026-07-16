import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { App } from "../App";
import type { ApiClient } from "../api";
import type { QueryResponse } from "../api/types";

const source = { id: "11111111-1111-1111-1111-111111111111", name: "Analytics warehouse",
  status: "active" as const, created_at: "2026-07-15T10:00:00Z" };

const result: QueryResponse = {
  query_run_id: "22222222-2222-2222-2222-222222222222",
  status: "completed",
  generated_sql: "SELECT region, SUM(revenue) AS total FROM sales GROUP BY region LIMIT 500",
  explanation: "Groups sales by region and totals revenue.",
  rows: [{ region: "North", total: 42000 }, { region: "South", total: 31000 }],
  columns: ["region", "total"], execution_time_ms: 12.4,
  confidence: {
    score: 0.87, policy_version: "v1", warnings: ["Independent SQL candidates disagree."],
    breakdown: [
      ["syntax_score", 1], ["schema_coverage", .9], ["execution_success", 1],
      ["hallucination_score", .85], ["multi_query_agreement", .55], ["explainability", .9],
    ].map(([name, raw]) => ({ name: String(name), raw_score: Number(raw), weight: 1 / 6,
                              contribution: Number(raw) / 6 })),
  },
  hallucination: null, warnings: ["Independent SQL candidates disagree."], violations: [],
  clarification_question: null,
};

function client(): ApiClient {
  return {
    listDataSources: vi.fn().mockResolvedValue([source]),
    history: vi.fn().mockResolvedValue({ items: [], limit: 50, offset: 0 }),
    runQuery: vi.fn().mockResolvedValue(result),
    executeEdited: vi.fn().mockResolvedValue({ ...result, generated_sql: "SELECT 2 LIMIT 500" }),
  };
}

describe("QueryForge dashboard", () => {
  beforeEach(() => localStorage.clear());

  it("loads data sources and shows the initial workspace", async () => {
    render(<App client={client()} />);
    expect(screen.getByRole("heading", { name: "Ask your data" })).toBeInTheDocument();
    expect(screen.getByText("Questions in. Answers out.")).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Analytics warehouse" })).toBeInTheDocument();
  });

  it("runs a natural-language query and renders SQL, rows, confidence, and warnings", async () => {
    const api = client();
    const user = userEvent.setup();
    render(<App client={api} />);
    await screen.findByRole("option", { name: "Analytics warehouse" });
    await user.type(screen.getByLabelText("Natural language question"), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /run query/i }));
    expect(await screen.findByRole("heading", { name: "Generated SQL" })).toBeInTheDocument();
    expect(screen.getByText("North")).toBeInTheDocument();
    expect(screen.getByText("87")).toBeInTheDocument();
    expect(screen.getByText("Schema coverage")).toBeInTheDocument();
    expect(screen.getByText("Independent SQL candidates disagree.")).toBeInTheDocument();
    expect(api.runQuery).toHaveBeenCalledWith(expect.objectContaining({
      data_source_id: source.id, question: "Revenue by region",
    }));
  });

  it("allows SQL editing and sends edited SQL through the execution endpoint", async () => {
    const api = client();
    const user = userEvent.setup();
    render(<App client={api} />);
    await screen.findByRole("option", { name: "Analytics warehouse" });
    await user.type(screen.getByLabelText("Natural language question"), "Revenue");
    await user.click(screen.getByRole("button", { name: /run query/i }));
    await screen.findByRole("heading", { name: "Generated SQL" });
    await user.click(screen.getByRole("button", { name: /edit/i }));
    const editor = screen.getByLabelText("Editable SQL");
    await user.clear(editor); await user.type(editor, "SELECT 2");
    await user.click(screen.getByRole("button", { name: /execute edited sql/i }));
    await waitFor(() => expect(api.executeEdited).toHaveBeenCalledWith(result.query_run_id, "SELECT 2"));
  });

  it("persists dark mode preference", async () => {
    const user = userEvent.setup();
    render(<App client={client()} />);
    await user.click(screen.getByRole("button", { name: "Switch to dark mode" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(localStorage.getItem("queryforge-theme")).toBe("dark");
  });
});
