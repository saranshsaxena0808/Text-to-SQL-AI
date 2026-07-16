import { ArrowUp, Database, Sparkles } from "lucide-react";
import type { DataSource } from "../api/types";

export function QuestionComposer({ question, onQuestion, sources, source, onSource,
  model, onModel, loading, onSubmit }: {
  question: string; onQuestion(value: string): void; sources: DataSource[];
  source: string; onSource(value: string): void; model: string; onModel(value: string): void;
  loading: boolean; onSubmit(): void;
}) {
  return <section className="composer-card" aria-labelledby="question-title">
    <div className="composer-title"><span><Sparkles size={17} /></span>
      <div><h2 id="question-title">What would you like to know?</h2>
        <p>Ask naturally. QueryForge will build and verify the SQL.</p></div>
    </div>
    <textarea value={question} onChange={(e) => onQuestion(e.target.value)}
      onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") onSubmit(); }}
      placeholder="e.g. Show monthly revenue by region for the last 12 months"
      aria-label="Natural language question" rows={4} />
    <div className="composer-controls">
      <label><Database size={15} /><span className="sr-only">Data source</span>
        <select value={source} onChange={(e) => onSource(e.target.value)} aria-label="Data source">
          {sources.length === 0 && <option value="">No data sources</option>}
          {sources.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <label><span className="sr-only">Model</span>
        <select value={model} onChange={(e) => onModel(e.target.value)} aria-label="Model">
          <option value="openai/gpt-oss-20b">GPT OSS 20B</option>
          <option value="openai/gpt-oss-120b">GPT OSS 120B</option>
          <option value="llama-3.3-70b-versatile">Llama 3.3 70B</option>
        </select>
      </label>
      <span className="shortcut">⌘ Enter</span>
      <button className="ask-button" disabled={loading || !question.trim() || !source} onClick={onSubmit}>
        {loading ? <span className="spinner" aria-label="Running query" /> : <ArrowUp size={18} />}
        <span>{loading ? "Analyzing" : "Run query"}</span>
      </button>
    </div>
  </section>;
}
