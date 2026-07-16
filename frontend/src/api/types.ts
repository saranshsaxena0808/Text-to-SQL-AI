export type QueryStatus = "completed" | "blocked" | "clarification_required" | "failed";

export interface ConfidenceComponent {
  name: string;
  raw_score: number;
  weight: number;
  contribution: number;
}

export interface ConfidenceAssessment {
  score: number;
  breakdown: ConfidenceComponent[];
  warnings: string[];
  policy_version: string;
}

export interface ValidationEvidence {
  check: string;
  available: boolean;
  risk: number;
  explanation: string;
  details: Record<string, unknown>;
}

export interface HallucinationAssessment {
  probability: number;
  explanation: string;
  evidence: ValidationEvidence[];
  policy_version: string;
}

export interface GuardrailViolation {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface QueryResponse {
  query_run_id: string;
  status: QueryStatus;
  generated_sql: string | null;
  explanation: string;
  rows: Record<string, unknown>[];
  columns: string[];
  execution_time_ms: number | null;
  confidence: ConfidenceAssessment | null;
  hallucination: HallucinationAssessment | null;
  warnings: string[];
  violations: GuardrailViolation[];
  clarification_question: string | null;
}

export interface QueryHistoryItem {
  id: string;
  data_source_id: string;
  question: string;
  generated_sql: string | null;
  status: QueryStatus;
  model: string | null;
  confidence: number | null;
  warnings: string[];
  timings: Record<string, number>;
  created_at: string;
}

export interface DataSource {
  id: string;
  name: string;
  status: "active" | "inactive" | "error";
  created_at: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details: unknown;
  request_id: string;
}
