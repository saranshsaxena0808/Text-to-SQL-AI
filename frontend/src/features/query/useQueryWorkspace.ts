import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../../api";
import type { DataSource, QueryHistoryItem, QueryResponse } from "../../api/types";

export function useQueryWorkspace(client: ApiClient) {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [selectedSource, setSelectedSource] = useState("");
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [sql, setSql] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    const page = await client.history();
    setHistory(page.items);
  }, [client]);

  useEffect(() => {
    let active = true;
    Promise.all([client.listDataSources(), client.history()])
      .then(([items, page]) => {
        if (!active) return;
        setSources(items);
        setHistory(page.items);
        setSelectedSource((current) => current || items[0]?.id || "");
      })
      .catch(() => active && setError("Could not load workspace data."));
    return () => { active = false; };
  }, [client]);

  async function ask(model: string) {
    if (!question.trim() || !selectedSource || loading) return;
    setLoading(true); setError(null);
    try {
      const response = await client.runQuery({
        data_source_id: selectedSource, question: question.trim(), model,
      });
      setResult(response); setSql(response.generated_sql ?? "");
      await refreshHistory();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Query failed.");
    } finally { setLoading(false); }
  }

  async function executeEdited() {
    if (!result || !sql.trim() || loading) return;
    setLoading(true); setError(null);
    try {
      const response = await client.executeEdited(result.query_run_id, sql.trim());
      setResult(response); setSql(response.generated_sql ?? sql);
      await refreshHistory();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "SQL execution failed.");
    } finally { setLoading(false); }
  }

  function openHistory(item: QueryHistoryItem) {
    setQuestion(item.question);
    setSelectedSource(item.data_source_id);
    setSql(item.generated_sql ?? "");
  }

  return { sources, history, selectedSource, setSelectedSource, question, setQuestion,
    result, sql, setSql, loading, error, ask, executeEdited, openHistory };
}
