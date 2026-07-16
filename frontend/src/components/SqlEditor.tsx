import { useState } from "react";
import { Check, Code2, Copy, Pencil, Play, X } from "lucide-react";
import { Highlight, themes } from "prism-react-renderer";

export function SqlEditor({ sql, onChange, onExecute, loading, dark }:
  { sql: string; onChange(value: string): void; onExecute(): void; loading: boolean; dark: boolean }) {
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard?.writeText(sql);
    setCopied(true); window.setTimeout(() => setCopied(false), 1400);
  }
  return <section className="panel sql-panel" aria-labelledby="sql-title">
    <header className="panel-head"><div><span className="panel-icon"><Code2 size={16} /></span>
      <span><h2 id="sql-title">Generated SQL</h2><p>Validated PostgreSQL query</p></span></div>
      <div className="panel-actions">
        <button className="ghost-button" onClick={copy}>{copied ? <Check size={15} /> : <Copy size={15} />}{copied ? "Copied" : "Copy"}</button>
        <button className="ghost-button" onClick={() => setEditing((value) => !value)}>
          {editing ? <X size={15} /> : <Pencil size={15} />}{editing ? "Cancel" : "Edit"}
        </button>
      </div>
    </header>
    {editing ? <div className="editor-mode">
      <textarea className="sql-textarea" aria-label="Editable SQL" value={sql}
                onChange={(event) => onChange(event.target.value)} rows={8} spellCheck={false} />
      <button className="execute-button" onClick={() => { onExecute(); setEditing(false); }}
              disabled={loading || !sql.trim()}><Play size={15} /> Execute edited SQL</button>
    </div> : <Highlight theme={dark ? themes.nightOwl : themes.github} code={sql} language="sql">
      {({ className, style, tokens, getLineProps, getTokenProps }) =>
        <pre className={`${className} sql-code`} style={style} tabIndex={0} aria-label="SQL preview">
          {tokens.map((line, index) => <div key={index} {...getLineProps({ line })}>
            <span className="line-number">{String(index + 1).padStart(2, "0")}</span>
            {line.map((token, key) => <span key={key} {...getTokenProps({ token })} />)}
          </div>)}
        </pre>}
    </Highlight>}
  </section>;
}
