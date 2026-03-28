export type PolicyCategory =
  | "hr_employment"
  | "data_protection"
  | "it_security"
  | "corporate_governance"
  | "health_safety";

export type Jurisdiction =
  | "us_delaware"
  | "us_california"
  | "uk"
  | "us_federal"
  | "us_new_york";

export type SessionStage =
  | "initialization"
  | "batch_analysis"
  | "plan_review"
  | "document_conversion"
  | "session_summary"
  | "completed";

export interface Session {
  id: string;
  created_at: string;
  updated_at: string;
  category: PolicyCategory;
  source_jurisdiction: Jurisdiction;
  stage: SessionStage;
  document_ids: string[];
  current_document_index: number;
  plan_approved: boolean;
}

export interface GapItem {
  clause_reference: string;
  original_text: string;
  issue_description: string;
  legal_citation: string;
  severity: "high" | "medium" | "low";
  confidence_score: number;
}

export interface ConvertedClause {
  clause_reference: string;
  original_text: string;
  converted_text: string;
  change_description: string;
  legal_citation: string;
  confidence_score: number;
}

export interface Document {
  id: string;
  session_id: string;
  filename: string;
  document_type?: string;
  status: string;
  gaps: GapItem[];
  converted_clauses: ConvertedClause[];
}
