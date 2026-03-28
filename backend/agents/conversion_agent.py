"""ConversionAgent — rewrites each document clause-by-clause for Irish/EU compliance."""

import logging
from datetime import datetime

from agents.llm_client import call_llm, parse_json_response
from config import REASONING_MODEL
from rag.retrieval import retrieve_relevant_law

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior Irish employment and data protection lawyer rewriting corporate
policy documents to comply with Irish and EU law.

You will be given:
1. An original policy clause from a foreign jurisdiction
2. The specific Irish/EU legal requirement it must comply with
3. The exact legal text from the relevant law

Your task: Rewrite the clause to be fully compliant while:
- Preserving the original intent and scope where legally possible
- Using clear, professional policy document language
- Explicitly incorporating the required legal standard
- Not adding obligations beyond what the law requires

Respond with JSON only: {"new_clause": "<the rewritten clause>", "plain_english_reason": "<one sentence a non-lawyer understands>"}"""

CONVERSION_PROMPT = """Rewrite this policy clause to comply with Irish/EU law.

ORIGINAL CLAUSE:
---
{original_clause}
---

COMPLIANCE GAP IDENTIFIED:
{gap_description}

REQUIRED ACTION:
{required_action}

RELEVANT LAW: {relevant_law}

LEGAL TEXT FROM KNOWLEDGE BASE:
---
{legal_context}
---

Rewrite the clause to be compliant. Preserve the original structure and intent where possible.
Return JSON only: {{"new_clause": "...", "plain_english_reason": "..."}}"""


def _get_legal_context_for_gap(relevant_law: str) -> tuple[str, str]:
    """Retrieve the actual legal text for a specific gap using targeted RAG."""
    results = retrieve_relevant_law(query=relevant_law, top_k=3)
    if not results:
        return "No specific legal text retrieved.", ""

    context_parts = []
    sources = []
    for r in results:
        context_parts.append(f"[{r.source_framework} — {r.section_title}]\n{r.chunk_text}")
        sources.append(f"{r.source_framework}: {r.section_title}")

    return "\n---\n".join(context_parts), "; ".join(sources[:2])


def _find_doc_gaps(doc_id: str, gap_analysis: list[dict]) -> list[dict]:
    """Find all non-compliant gaps for a specific document."""
    for report in gap_analysis:
        if report.get("doc_id") == doc_id:
            return [g for g in report.get("gaps", []) if not g.get("is_compliant", True)]
    return []


def _find_planned_changes(doc_id: str, conversion_plan: dict) -> list[dict]:
    """Find planned changes for a document from the conversion plan."""
    for da in conversion_plan.get("per_document_actions", []):
        if da.get("doc_id") == doc_id:
            return da.get("planned_changes", [])
    return []


def _apply_changes_to_document(original_text: str, changes: list[dict]) -> str:
    """Reconstruct the full document by replacing original clauses with converted versions."""
    converted = original_text
    for change in changes:
        original_clause = change.get("original_clause", "")
        new_clause = change.get("new_clause", "")
        if original_clause and new_clause and original_clause in converted:
            converted = converted.replace(original_clause, new_clause, 1)
    return converted


def run_conversion_agent(state: dict) -> dict:
    """Convert the current document clause-by-clause."""
    idx = state.get("current_doc_index", 0)
    docs = state.get("uploaded_documents", [])
    gap_analysis = state.get("gap_analysis", [])
    conversion_plan = state.get("conversion_plan", {})
    messages = list(state.get("agent_messages", []))
    errors = list(state.get("errors", []))

    if idx >= len(docs):
        errors.append(f"Document index {idx} out of range")
        return {"agent_messages": messages, "errors": errors}

    doc = docs[idx]
    doc_id = doc["doc_id"]
    filename = doc["filename"]
    original_text = doc.get("raw_text", "")

    messages.append(f"[conversion] Converting '{filename}' (doc {idx + 1}/{len(docs)})")
    logger.info(f"[conversion] Processing {filename}")

    # Get gaps and planned changes
    gaps = _find_doc_gaps(doc_id, gap_analysis)
    planned_changes = _find_planned_changes(doc_id, conversion_plan)

    logger.info(f"[conversion] {filename}: {len(gaps)} gaps to convert")

    changes = []
    flagged_for_solicitor = []
    change_counter = 0

    for gap in gaps:
        change_counter += 1
        change_id = f"DOC{idx + 1}-CHG-{change_counter:03d}"
        clause_text = gap.get("clause_text", "")
        relevant_law = gap.get("relevant_law", "")
        gap_description = gap.get("gap_description", "")
        required_action = gap.get("required_action", "")
        confidence = gap.get("confidence", 50)

        # Get legal context from RAG
        legal_context, citation_source = _get_legal_context_for_gap(relevant_law)

        try:
            response_text = call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=CONVERSION_PROMPT.format(
                    original_clause=clause_text,
                    gap_description=gap_description,
                    required_action=required_action,
                    relevant_law=relevant_law,
                    legal_context=legal_context[:2000],
                ),
                model=REASONING_MODEL,
                agent_name="conversion",
                temperature=0.1,
            )
            result = parse_json_response(response_text)
            new_clause = result.get("new_clause", clause_text)
            plain_reason = result.get("plain_english_reason", gap_description)

            # Determine change type
            change_type = "Modified"
            if confidence < 70:
                change_type = "Flagged"
                flagged_for_solicitor.append({
                    "change_id": change_id,
                    "issue": gap_description[:150],
                    "reason": f"Low confidence ({confidence}%) — requires legal review",
                })

            changes.append({
                "change_id": change_id,
                "original_clause": clause_text,
                "new_clause": new_clause,
                "legal_citation": relevant_law,
                "citation_excerpt": legal_context[:300],
                "plain_english_reason": plain_reason,
                "change_type": change_type,
                "confidence": confidence,
            })

        except Exception as e:
            logger.error(f"[conversion] Failed converting clause {change_id}: {e}")
            errors.append(f"Conversion failed for {change_id} in {filename}: {str(e)}")
            changes.append({
                "change_id": change_id,
                "original_clause": clause_text,
                "new_clause": clause_text,  # Keep original on failure
                "legal_citation": relevant_law,
                "citation_excerpt": "",
                "plain_english_reason": f"Conversion failed: {str(e)}",
                "change_type": "Flagged",
                "confidence": 0,
            })
            flagged_for_solicitor.append({
                "change_id": change_id,
                "issue": f"Automated conversion failed for this clause",
                "reason": str(e)[:200],
            })

    # Assemble the converted document
    converted_text = _apply_changes_to_document(original_text, changes)

    # Add compliance header
    header = f"""[POLICYBRIDGE COMPLIANCE CONVERSION]
Converted: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Source Jurisdiction: {state.get('source_jurisdiction', 'Unknown')}
Target Jurisdiction: Ireland / European Union
Total Changes: {len(changes)}
This document was converted by PolicyBridge AI. All changes require human legal review
before adoption. Items marked [SOLICITOR REVIEW REQUIRED] must be reviewed by a
qualified Irish solicitor before implementation.
{'=' * 60}

"""
    converted_text = header + converted_text

    unchanged_count = len([g for g in (gap_analysis[idx]["gaps"] if idx < len(gap_analysis) else []) if g.get("is_compliant", True)]) if idx < len(gap_analysis) else 0

    converted_doc = {
        "doc_id": doc_id,
        "filename": filename,
        "status": "converted",
        "original_text": original_text,
        "converted_text": converted_text,
        "changes": changes,
        "unchanged_clauses_count": unchanged_count,
        "total_changes": len(changes),
        "flagged_for_solicitor": flagged_for_solicitor,
    }

    # Update converted_documents list
    existing = list(state.get("converted_documents", []))
    replaced = False
    for i, c in enumerate(existing):
        if c["doc_id"] == doc_id:
            existing[i] = converted_doc
            replaced = True
            break
    if not replaced:
        existing.append(converted_doc)

    messages.append(f"[conversion] '{filename}': {len(changes)} changes made, {len(flagged_for_solicitor)} flagged for solicitor")
    logger.info(f"[conversion] {filename}: {len(changes)} changes, {len(flagged_for_solicitor)} solicitor flags")

    return {
        "converted_documents": existing,
        "current_stage": "awaiting_doc_approval",
        "agent_messages": messages,
        "errors": errors,
    }
