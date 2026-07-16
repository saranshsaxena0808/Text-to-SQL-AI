import { useState } from "react";
import type { ApiClient } from "./api";
import { api } from "./api";
import { ConfidenceCard } from "./components/ConfidenceCard";
import { HistorySidebar } from "./components/HistorySidebar";
import { QuestionComposer } from "./components/QuestionComposer";
import { ResultTable } from "./components/ResultTable";
import { SqlEditor } from "./components/SqlEditor";
import { Topbar } from "./components/Topbar";
import { Warnings } from "./components/Warnings";
import { WelcomeState } from "./components/WelcomeState";
import { useQueryWorkspace } from "./features/query/useQueryWorkspace";
import { useTheme } from "./hooks/useTheme";

export function App({ client = api }: { client?: ApiClient }) {
  const workspace = useQueryWorkspace(client);
  const { theme, toggleTheme } = useTheme();
  const [sidebar, setSidebar] = useState(false);
  const [model, setModel] = useState(import.meta.env.VITE_DEFAULT_MODEL ?? "openai/gpt-oss-20b");
  const result = workspace.result;
  function reset() { workspace.setQuestion(""); workspace.setSql(""); setSidebar(false); }
  return <div className="app-shell">
    <HistorySidebar history={workspace.history} open={sidebar} onClose={() => setSidebar(false)}
      onNew={reset} onSelect={(item) => { workspace.openHistory(item); setSidebar(false); }} />
    {sidebar && <button className="scrim" aria-label="Close navigation" onClick={() => setSidebar(false)} />}
    <main className="workspace">
      <Topbar theme={theme} onToggleTheme={toggleTheme} onToggleSidebar={() => setSidebar(true)} />
      <div className="content">
        <QuestionComposer question={workspace.question} onQuestion={workspace.setQuestion}
          sources={workspace.sources} source={workspace.selectedSource} onSource={workspace.setSelectedSource}
          model={model} onModel={setModel} loading={workspace.loading} onSubmit={() => workspace.ask(model)} />
        {workspace.error && <div className="error-banner" role="alert">{workspace.error}</div>}
        {!result && !workspace.sql && <WelcomeState />}
        {(result || workspace.sql) && <div className="answer-grid">
          <div className="answer-main">
            {(result ? result.generated_sql !== null : Boolean(workspace.sql)) && <SqlEditor sql={workspace.sql} onChange={workspace.setSql}
              onExecute={workspace.executeEdited} loading={workspace.loading} dark={theme === "dark"} />}
            <Warnings warnings={[...(result?.warnings ?? []), ...(result?.violations.map((v) => v.message) ?? [])]}
                      clarification={result?.clarification_question} />
            {result && <ResultTable rows={result.rows} columns={result.columns}
                                    executionTime={result.execution_time_ms} />}
          </div>
          <aside className="answer-side">{result?.confidence && <ConfidenceCard confidence={result.confidence} />}
            {result?.explanation && <section className="panel explanation"><h2>Why this query?</h2><p>{result.explanation}</p></section>}
          </aside>
        </div>}
      </div>
    </main>
  </div>;
}
