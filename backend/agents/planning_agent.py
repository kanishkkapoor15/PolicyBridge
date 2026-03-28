"""PlanningAgent — synthesises gap analysis into a human-readable conversion plan."""

import logging

from agents.llm_client import call_llm, parse_json_response
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a compliance project manager preparing a briefing for a senior auditor.
Your job is to take detailed legal gap analysis and present it as a clear,
actionable conversion plan in plain English.

Write for a reader who understands business and compliance but is not a lawyer.
Be specific about what will change but avoid excessive legal jargon.
Every proposed change must clearly state what law requires it.
Always respond with valid JSON only."""

PLAN_PROMPT_TEMPLATE = """Based on the gap analysis below, create a conversion plan.

Source jurisdiction: {source_jurisdiction}
Target jurisdiction: Ireland / European Union
Policy category: {policy_category}

CONFLICTS BETWEEN DOCUMENTS:
{conflicts_text}

GAP ANALYSIS PER DOCUMENT:
{gap_analysis_text}

Return a JSON object:
{{
  "summary": "2-3 sentence executive summary of the overall compliance situation",
  "risk_level": "Low|Medium|High",
  "per_document_actions": [
    {{
      "doc_id": "<doc_id>",
      "filename": "<filename>",
      "doc_type": "<doc_type>",
      "gap_count": <int>,
      "planned_changes": [
        {{
          "change_id": "DOC<n>-CHG-<nnn>",
          "current_clause_summary": "plain English: what the doc currently says",
          "proposed_change_summary": "plain English: what it will say after conversion",
          "legal_basis": "specific law and section",
          "impact": "Minor|Moderate|Major",
          "confidence": <int 0-100>
        }}
      ]
    }}
  ],
  "items_requiring_solicitor_review": [
    {{
      "doc_id": "<doc_id>",
      "issue": "description",
      "reason": "why this needs human legal judgment"
    }}
  ]
}}

Respond with JSON only."""


def _format_conflicts(conflicts: list[dict]) -> str:
    if not conflicts:
        return "No intra-batch conflicts detected."
    parts = []
    for c in conflicts:
        parts.append(f"- [{c.get('severity', 'unknown').upper()}] {c.get('doc_a_name', '?')} vs {c.get('doc_b_name', '?')}: {c.get('conflict_description', '')}")
    return "\n".join(parts)


def _format_gap_analysis(gap_analysis: list[dict]) -> str:
    parts = []
    for doc_report in gap_analysis:
        parts.append(f"\n## {doc_report.get('filename', 'Unknown')} ({doc_report.get('total_clauses_analysed', 0)} clauses, {doc_report.get('non_compliant_clauses', 0)} non-compliant)")
        for gap in doc_report.get("gaps", []):
            if not gap.get("is_compliant", True):
                parts.append(f"  - [{gap.get('confidence', 0)}%] {gap.get('clause_heading', 'Unknown')}: {gap.get('gap_description', '')[:200]}")
                parts.append(f"    Law: {gap.get('relevant_law', 'N/A')}")
                parts.append(f"    Action: {gap.get('required_action', 'N/A')[:200]}")
    return "\n".join(parts)


def _flag_solicitor_items(gap_analysis: list[dict]) -> list[dict]:
    """Flag items requiring solicitor review based on confidence, topic, or deletion risk."""
    solicitor_items = []
    solicitor_keywords = ["pension", "redundancy", "tupe", "transfer of undertaking",
                          "collective agreement", "trade union recognition"]

    for doc_report in gap_analysis:
        for gap in doc_report.get("gaps", []):
            if gap.get("is_compliant", True):
                continue

            needs_solicitor = False
            reason = ""

            if gap.get("confidence", 100) < 70:
                needs_solicitor = True
                reason = f"Low confidence ({gap['confidence']}%) — agent uncertain about this gap"

            action = (gap.get("required_action", "") + " " + gap.get("gap_description", "")).lower()
            for kw in solicitor_keywords:
                if kw in action:
                    needs_solicitor = True
                    reason = f"Involves {kw} — requires case-law interpretation"
                    break

            if any(phrase in action for phrase in ["remove entirely", "delete", "remove the clause", "remove this section"]):
                needs_solicitor = True
                reason = "Clause deletion is higher risk than modification"

            if needs_solicitor:
                solicitor_items.append({
                    "doc_id": doc_report.get("doc_id", ""),
                    "issue": f"{gap.get('clause_heading', 'Unknown')}: {gap.get('gap_description', '')[:150]}",
                    "reason": reason,
                })

    return solicitor_items


def run_planning_agent(state: dict) -> dict:
    """Generate a human-readable conversion plan from gap analysis."""
    gap_analysis = state.get("gap_analysis", [])
    conflicts = state.get("intra_batch_conflicts", [])
    docs = state.get("uploaded_documents", [])
    messages = list(state.get("agent_messages", []))
    errors = list(state.get("errors", []))

    messages.append(f"[planning] Generating conversion plan for {len(docs)} documents")
    logger.info(f"[planning] Building plan from {sum(r.get('non_compliant_clauses', 0) for r in gap_analysis)} gaps")

    # Build doc_type lookup
    doc_types = {d["doc_id"]: d.get("doc_type", "Unknown") for d in docs}

    conflicts_text = _format_conflicts(conflicts)
    gap_text = _format_gap_analysis(gap_analysis)

    try:
        response_text = call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=PLAN_PROMPT_TEMPLATE.format(
                source_jurisdiction=state.get("source_jurisdiction", "unknown"),
                policy_category=state.get("policy_category", "unknown"),
                conflicts_text=conflicts_text,
                gap_analysis_text=gap_text,
            ),
            model=CHAT_MODEL,
            agent_name="planning",
        )
        plan = parse_json_response(response_text)

        # Enrich with metadata
        plan["source_jurisdiction"] = state.get("source_jurisdiction", "")
        plan["target_jurisdiction"] = "ireland_eu"
        plan["total_documents"] = len(docs)
        plan["total_gaps_found"] = sum(r.get("non_compliant_clauses", 0) for r in gap_analysis)
        plan["estimated_changes"] = sum(
            len(da.get("planned_changes", []))
            for da in plan.get("per_document_actions", [])
        )

        # Add doc_type to each per_document_actions entry
        for da in plan.get("per_document_actions", []):
            if "doc_type" not in da or not da["doc_type"]:
                da["doc_type"] = doc_types.get(da.get("doc_id", ""), "Unknown")

        # Add solicitor items from our heuristic if model didn't produce them
        heuristic_solicitor = _flag_solicitor_items(gap_analysis)
        existing_solicitor = plan.get("items_requiring_solicitor_review", [])
        if not existing_solicitor and heuristic_solicitor:
            plan["items_requiring_solicitor_review"] = heuristic_solicitor
        elif heuristic_solicitor:
            existing_ids = {(s.get("doc_id"), s.get("issue", "")[:50]) for s in existing_solicitor}
            for item in heuristic_solicitor:
                key = (item["doc_id"], item["issue"][:50])
                if key not in existing_ids:
                    existing_solicitor.append(item)

        messages.append(f"[planning] Plan ready: {plan.get('estimated_changes', 0)} changes across {len(docs)} documents, risk level: {plan.get('risk_level', 'Unknown')}")

    except Exception as e:
        logger.error(f"[planning] Failed to generate plan: {e}")
        errors.append(f"Planning agent failed: {str(e)}")
        plan = {
            "summary": "Plan generation failed — please retry",
            "risk_level": "High",
            "source_jurisdiction": state.get("source_jurisdiction", ""),
            "target_jurisdiction": "ireland_eu",
            "total_documents": len(docs),
            "total_gaps_found": sum(r.get("non_compliant_clauses", 0) for r in gap_analysis),
            "estimated_changes": 0,
            "per_document_actions": [],
            "items_requiring_solicitor_review": [],
        }
        messages.append("[planning] Plan generation failed")

    return {
        "conversion_plan": plan,
        "current_stage": "awaiting_plan_approval",
        "agent_messages": messages,
        "errors": errors,
    }
