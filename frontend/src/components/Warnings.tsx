import { AlertTriangle, HelpCircle } from "lucide-react";

export function Warnings({ warnings, clarification }:
  { warnings: string[]; clarification?: string | null }) {
  const items = clarification ? [clarification, ...warnings] : warnings;
  if (!items.length) return null;
  return <section className="warnings" aria-live="polite" aria-label="Query warnings">
    {items.map((warning, index) => <div key={`${warning}-${index}`}>
      {clarification && index === 0 ? <HelpCircle size={17} /> : <AlertTriangle size={17} />}
      <span>{warning}</span>
    </div>)}
  </section>;
}
