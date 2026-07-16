import { Clock3, Plus, X } from "lucide-react";
import type { QueryHistoryItem } from "../api/types";
import { Brand } from "./Brand";

export function HistorySidebar({ history, open, onClose, onSelect, onNew }:
  { history: QueryHistoryItem[]; open: boolean; onClose(): void;
    onSelect(item: QueryHistoryItem): void; onNew(): void }) {
  return <aside className={`sidebar ${open ? "is-open" : ""}`} aria-label="Query history">
    <div className="sidebar-head"><Brand />
      <button className="icon-button mobile-only" onClick={onClose} aria-label="Close history"><X size={18} /></button>
    </div>
    <button className="new-query" onClick={onNew}><Plus size={17} /> New question</button>
    <div className="section-label"><Clock3 size={14} /> Recent queries</div>
    <nav className="history-list">
      {history.length === 0 && <p className="empty-copy">Your recent questions will appear here.</p>}
      {history.map((item) => <button key={item.id} className="history-item" onClick={() => onSelect(item)}>
        <span>{item.question}</span>
        <small>{new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(item.created_at))}</small>
      </button>)}
    </nav>
    <div className="sidebar-foot"><kbd>⌘</kbd><kbd>K</kbd><span>Quick search</span></div>
  </aside>;
}
