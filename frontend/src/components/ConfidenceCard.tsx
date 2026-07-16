import { Activity, ShieldCheck } from "lucide-react";
import type { ConfidenceAssessment } from "../api/types";

const LABELS: Record<string, string> = {
  syntax_score: "Syntax", schema_coverage: "Schema coverage", execution_success: "Execution",
  hallucination_score: "Grounding", multi_query_agreement: "Query agreement",
  explainability: "Explainability",
};

export function ConfidenceCard({ confidence }: { confidence: ConfidenceAssessment }) {
  const percent = Math.round(confidence.score * 100);
  const tone = percent >= 80 ? "strong" : percent >= 60 ? "medium" : "low";
  return <section className="panel confidence-panel" aria-labelledby="confidence-title">
    <header className="panel-head"><div><span className="panel-icon"><ShieldCheck size={16} /></span>
      <span><h2 id="confidence-title">Confidence</h2><p>Policy {confidence.policy_version}</p></span></div></header>
    <div className={`confidence-score ${tone}`}>
      <div className="score-ring" style={{ "--score": `${percent * 3.6}deg` } as React.CSSProperties}>
        <span><strong>{percent}</strong><small>%</small></span>
      </div>
      <div><strong>{tone === "strong" ? "High confidence" : tone === "medium" ? "Review suggested" : "Low confidence"}</strong>
        <p>Based on six independent quality signals.</p></div>
    </div>
    <div className="breakdown" aria-label="Confidence breakdown">
      {confidence.breakdown.map((item) => <div className="metric" key={item.name}>
        <div><span>{LABELS[item.name] ?? item.name}</span><strong>{Math.round(item.raw_score * 100)}%</strong></div>
        <progress max="1" value={item.raw_score}>{item.raw_score}</progress>
      </div>)}
    </div>
    <div className="confidence-foot"><Activity size={14} /> Weighted contribution model</div>
  </section>;
}
