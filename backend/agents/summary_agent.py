"""SummaryAgent — generates final compliance report and marks session complete."""

import logging
from datetime import datetime

from agents.llm_client import call_llm, parse_json_response
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a compliance report writer preparing a final executive summary
for a policy conversion project.

Write concisely for a C-suite audience. Focus on: what was done, the overall compliance
improvement, key risk areas remaining, and recommended next steps.
Always respond with valid JSON only."""

SUMMARY_PROMPT = """Generate a final compliance report summary based on this session data.

Session overview:
- Source jurisdiction: {source_jurisdiction}
- Target: Ireland / EU
- Category: {policy_category}
- Documents processed: {doc_count}

Gap analysis summary:
{gap_summary}

Changes made summary:
{changes_summary}

Items flagged for solicitor:
{solicitor_summary}

Return JSON:
{{
  "executive_summary": "3-5 sentences for C-suite — overall outcome, key risks, confidence level",
  "changes_by_framework": {{"framework_name": count}},
  "next_steps": ["recommended actions for the auditor"]
}}

JSON only."""


def _compute_compliance_scores(gap_analysis: list[dict], converted_documents: list[dict]) -> tuple[int, int]:
    """Compute before/after compliance scores."""
    total_clauses = 0
    non_compliant_before = 0
    for report in gap_analysis:
        total_clauses += report.get("total_clauses_analysed", 0)
        non_compliant_before += report.get("non_compliant_clauses", 0)

    if total_clauses == 0:
        return 100, 100

    score_before = max(0, int(((total_clauses - non_compliant_before) / total_clauses) * 100))

    # After: count remaining flagged items (low confidence or failed conversions)
    remaining_issues = 0
    for doc in converted_documents:
        remaining_issues += len(doc.get("flagged_for_solicitor", []))
        for change in doc.get("changes", []):
            if change.get("confidence", 100) < 60:
                remaining_issues += 1

    score_after = max(score_before, min(100, int(((total_clauses - remaining_issues) / total_clauses) * 100)))

    return score_before, score_after


def _build_gap_summary(gap_analysis: list[dict]) -> str:
    parts = []
    for report in gap_analysis:
        parts.append(f"  {report.get('filename', '?')}: {report.get('non_compliant_clauses', 0)}/{report.get('total_clauses_analysed', 0)} non-compliant")
    return "\n".join(parts) if parts else "No gaps found"


def _build_changes_summary(converted_documents: list[dict]) -> str:
    parts = []
    for doc in converted_documents:
        parts.append(f"  {doc.get('filename', '?')}: {doc.get('total_changes', 0)} changes made")
        for change in doc.get("changes", [])[:3]:
            parts.append(f"    - {change.get('change_id', '?')}: {change.get('plain_english_reason', '')[:100]} ({change.get('legal_citation', 'N/A')})")
    return "\n".join(parts) if parts else "No conversions completed"


def _build_solicitor_summary(converted_documents: list[dict]) -> str:
    items = []
    for doc in converted_documents:
        for flag in doc.get("flagged_for_solicitor", []):
            items.append(f"  - {doc.get('filename', '?')}: {flag.get('issue', '')[:100]} — {flag.get('reason', '')}")
    return "\n".join(items) if items else "No items flagged"


def _count_changes_by_framework(converted_documents: list[dict]) -> dict[str, int]:
    """Count changes grouped by legal framework from citations."""
    framework_counts: dict[str, int] = {}
    framework_keywords = {
        "GDPR": ["gdpr", "general data protection"],
        "OWTA": ["organisation of working time", "working time act"],
        "EEA": ["employment equality", "equality act"],
        "DPA 2018": ["data protection act 2018"],
        "NIS2": ["nis2", "network and information"],
        "EU AI Act": ["ai act", "artificial intelligence act"],
        "DPC Guidance": ["dpc", "data protection commission"],
        "Companies Act": ["companies act"],
    }
    for doc in converted_documents:
        for change in doc.get("changes", []):
            citation = (change.get("legal_citation", "") + " " + change.get("plain_english_reason", "")).lower()
            matched = False
            for framework, keywords in framework_keywords.items():
                if any(kw in citation for kw in keywords):
                    framework_counts[framework] = framework_counts.get(framework, 0) + 1
                    matched = True
                    break
            if not matched:
                framework_counts["Other"] = framework_counts.get("Other", 0) + 1
    return framework_counts


def run_summary_agent(state: dict) -> dict:
    """Generate final compliance report and mark session complete."""
    gap_analysis = state.get("gap_analysis", [])
    converted = state.get("converted_documents", [])
    docs = state.get("uploaded_documents", [])
    messages = list(state.get("agent_messages", []))
    errors = list(state.get("errors", []))

    messages.append("[summary] Generating final compliance report")
    logger.info("[summary] Building final report")

    score_before, score_after = _compute_compliance_scores(gap_analysis, converted)
    changes_by_framework = _count_changes_by_framework(converted)

    try:
        response_text = call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=SUMMARY_PROMPT.format(
                source_jurisdiction=state.get("source_jurisdiction", "unknown"),
                policy_category=state.get("policy_category", "unknown"),
                doc_count=len(docs),
                gap_summary=_build_gap_summary(gap_analysis),
                changes_summary=_build_changes_summary(converted),
                solicitor_summary=_build_solicitor_summary(converted),
            ),
            model=CHAT_MODEL,
            agent_name="summary",
        )
        result = parse_json_response(response_text)
        executive_summary = result.get("executive_summary", "Report generation completed.")
        next_steps = result.get("next_steps", ["Review all converted documents", "Consult solicitor for flagged items"])

        # Merge LLM framework counts with our computed ones
        llm_frameworks = result.get("changes_by_framework", {})
        if llm_frameworks:
            for fw, count in llm_frameworks.items():
                if fw not in changes_by_framework:
                    changes_by_framework[fw] = count

    except Exception as e:
        logger.error(f"[summary] Failed to generate summary: {e}")
        errors.append(f"Summary agent failed: {str(e)}")
        executive_summary = f"Processed {len(converted)} documents with {sum(d.get('total_changes', 0) for d in converted)} total changes."
        next_steps = ["Review all converted documents", "Consult solicitor for flagged items"]

    # Build documents summary
    documents_summary = []
    for doc in converted:
        solicitor_count = len(doc.get("flagged_for_solicitor", []))
        status = "Converted"
        if solicitor_count > 2:
            status = "Partially Converted"
        elif solicitor_count > 0:
            status = "Flagged"

        # Find matching gap report
        gaps_found = 0
        for report in gap_analysis:
            if report.get("doc_id") == doc.get("doc_id"):
                gaps_found = report.get("non_compliant_clauses", 0)
                break

        documents_summary.append({
            "filename": doc.get("filename", ""),
            "gaps_found": gaps_found,
            "changes_made": doc.get("total_changes", 0),
            "solicitor_items": solicitor_count,
            "status": status,
        })

    # Consolidated outstanding issues
    outstanding_issues = []
    for doc in converted:
        for flag in doc.get("flagged_for_solicitor", []):
            outstanding_issues.append({
                "doc_id": doc.get("doc_id", ""),
                "filename": doc.get("filename", ""),
                "issue": flag.get("issue", ""),
                "reason": flag.get("reason", ""),
                "requires_solicitor": True,
            })
    # Sort by confidence (lower confidence = higher priority)
    outstanding_issues.sort(key=lambda x: "Low confidence" in x.get("reason", ""), reverse=True)

    final_report = {
        "session_id": state.get("session_id", ""),
        "generated_at": datetime.now().isoformat(),
        "executive_summary": executive_summary,
        "compliance_score_before": score_before,
        "compliance_score_after": score_after,
        "total_documents_processed": len(converted),
        "total_gaps_identified": sum(r.get("non_compliant_clauses", 0) for r in gap_analysis),
        "total_changes_made": sum(d.get("total_changes", 0) for d in converted),
        "changes_by_framework": changes_by_framework,
        "documents_summary": documents_summary,
        "next_steps": next_steps,
    }

    messages.append(f"[summary] Report complete — score: {score_before}% → {score_after}%")
    logger.info(f"[summary] Final scores: {score_before}% → {score_after}%")

    return {
        "final_report": final_report,
        "outstanding_issues": outstanding_issues,
        "export_ready": True,
        "current_stage": "complete",
        "agent_messages": messages,
        "errors": errors,
    }
