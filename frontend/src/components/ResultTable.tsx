import { Download, Table2 } from "lucide-react";

function display(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ResultTable({ rows, columns, executionTime }:
  { rows: Record<string, unknown>[]; columns: string[]; executionTime: number | null }) {
  function downloadCsv() {
    const escape = (value: unknown) => `"${display(value).replaceAll('"', '""')}"`;
    const csv = [columns.map(escape).join(","), ...rows.map((row) => columns.map((c) => escape(row[c])).join(","))].join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = "query-results.csv"; link.click(); URL.revokeObjectURL(link.href);
  }
  return <section className="panel result-panel" aria-labelledby="results-title">
    <header className="panel-head"><div><span className="panel-icon"><Table2 size={16} /></span>
      <span><h2 id="results-title">Results</h2><p>{rows.length.toLocaleString()} rows · {executionTime?.toFixed(1) ?? "—"} ms</p></span></div>
      <button className="ghost-button" onClick={downloadCsv} disabled={!rows.length}><Download size={15} /> Export CSV</button>
    </header>
    <div className="table-scroll">
      <table><thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) =>
          <td key={column} title={display(row[column])}>{display(row[column])}</td>)}</tr>)}</tbody>
      </table>
      {!rows.length && <div className="empty-results"><Table2 size={26} /><strong>No rows returned</strong><span>The query executed successfully.</span></div>}
    </div>
  </section>;
}
