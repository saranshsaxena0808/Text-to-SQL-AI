import { BarChart3, ShieldCheck, WandSparkles } from "lucide-react";

export function WelcomeState() {
  return <section className="welcome" aria-label="Getting started">
    <div><WandSparkles /><h2>Questions in. Answers out.</h2><p>QueryForge translates natural language into safe, verified SQL.</p></div>
    <ul><li><ShieldCheck /><span><strong>Guardrailed</strong>Read-only queries and plan checks</span></li>
      <li><BarChart3 /><span><strong>Explainable</strong>Confidence for every answer</span></li></ul>
  </section>;
}
