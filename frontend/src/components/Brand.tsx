import { DatabaseZap } from "lucide-react";

export function Brand() {
  return <div className="brand" aria-label="QueryForge home">
    <span className="brand-mark"><DatabaseZap size={20} aria-hidden="true" /></span>
    <span><strong>QueryForge</strong><small>AI data workspace</small></span>
  </div>;
}
