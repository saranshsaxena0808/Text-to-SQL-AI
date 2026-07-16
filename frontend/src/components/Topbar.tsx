import { Moon, Sun, PanelLeft } from "lucide-react";
import type { Theme } from "../hooks/useTheme";

export function Topbar({ theme, onToggleTheme, onToggleSidebar }:
  { theme: Theme; onToggleTheme(): void; onToggleSidebar(): void }) {
  return <header className="topbar">
    <button className="icon-button mobile-only" onClick={onToggleSidebar} aria-label="Open history">
      <PanelLeft size={19} />
    </button>
    <div><p className="eyebrow">Workspace</p><h1>Ask your data</h1></div>
    <div className="topbar-actions">
      <span className="system-status"><i /> Systems operational</span>
      <button className="icon-button" onClick={onToggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </button>
      <span className="avatar" aria-label="Current user">HQ</span>
    </div>
  </header>;
}
