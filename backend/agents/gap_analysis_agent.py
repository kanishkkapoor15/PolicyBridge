"""GapAnalysisAgent — compares each document against Irish/EU legal corpus via RAG."""

import logging
import re

from agents.llm_client import call_llm, parse_json_response
from config import REASONING_MODEL
from rag.retrieval import retrieve_for_policy_category

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior compliance lawyer specialising in Irish and EU law.
You are reviewing corporate policy documents from foreign jurisdictions
for compliance with Irish and EU legal requirements.

For each policy clause provided, you will:
1. Identify specific compliance gaps against the provided Irish/EU legal context
2. Cite the exact law, directive, or article that applies
3. Describe precisely what change is required
4. Assign a confidence score (0-100) reflecting certainty of the gap

Be precise and conservative. Only flag genuine legal compliance issues,
not stylistic differences. If a clause is compliant, say so clearly.
Always respond with valid JSON only."""

CLAUSE_ANALYSIS_PROMPT = """Analyse the following policy clause from a {source_jurisdiction} company for compliance with Irish and EU law.

Source jurisdiction: {source_jurisdiction}
Policy category: {policy_category}

POLICY CLAUSE:
---
{clause_text}
---

RELEVANT IRISH/EU LEGAL CONTEXT (from knowledge base):
---
{legal_context}
---

Return a JSON object:
{{
  "gaps": [
    {{
      "is_compliant": false,
      "gap_description": "specific description of the compliance gap",
      "relevant_law": "exact law/article (e.g. 'GDPR Article 6(1)(a)', 'Employment Equality Acts 1998-2015, Section 16')",
      "required_action": "what specifically needs to change in this clause",
      "confidence": 85
    }}
  ]
}}

If the clause is fully compliant, return: {{"gaps": [{{"is_compliant": true, "gap_description": "No compliance gap identified", "relevant_law": "N/A", "required_action": "None required", "confidence": 95}}]}}

Return the JSON object only."""


def _split_into_clauses(text: str) -> list[dict]:
    """Split document text into logical clauses/sections by headings and paragraph boundaries."""
    lines = text.split("\n")
    clauses = []
    current_heading = "General"
    current_lines: list[str] = []

    def flush():
        body = "\n".join(current_lines).strip()
        if body and len(body.split()) >= 15:  # Skip very short fragments
            clauses.append({"heading": current_heading, "text": body})

    for line in lines:
        stripped = line.strip()
        # Detect headings: numbered sections, ALL CAPS lines, or markdown-style
        is_heading = False
        if stripped and (
            re.match(r"^#{1,4}\s+", stripped) or
            re.match(r"^\d+[\.\)]\s+[A-Z]", stripped) or
            (stripped.isupper() and len(stripped.split()) <= 10 and len(stripped) > 3) or
            re.match(r"^(Section|Article|Part|Chapter)\s+\d+", stripped, re.IGNORECASE)
        ):
            is_heading = True

        if is_heading:
            flush()
            current_heading = stripped.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    flush()

    # If no clauses were found (unstructured text), split by double newlines
    if not clauses:
        paragraphs = re.split(r"\n\s*\n", text)
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if len(para.split()) >= 15:
                clauses.append({"heading": f"Paragraph {i + 1}", "text": para})

    return clauses


def _build_legal_context(clause_text: str, category: str) -> str:
    """Retrieve relevant legal context for a clause using the RAG pipeline."""
    results = retrieve_for_policy_category(category, clause_text, top_k=5)
    if not results:
        return "No specific legal context retrieved."

    context_parts = []
    for r in results:
        context_parts.append(
            f"[{r.source_framework} — {r.section_title}] (relevance: {r.relevance_score:.2f})\n{r.chunk_text}\n"
        )
    return "\n---\n".join(context_parts)


def run_gap_analysis_agent(state: dict) -> dict:
    """Run gap analysis on all documents using RAG + reasoning model."""
    docs = state.get("uploaded_documents", [])
    category = state.get("policy_category", "hr_employment")
    source_jurisdiction = state.get("source_jurisdiction", "unknown")
    messages = list(state.get("agent_messages", []))
    errors = list(state.get("errors", []))

    messages.append(f"[gap_analysis] Starting gap analysis for {len(docs)} documents")
    logger.info(f"[gap_analysis] Analysing {len(docs)} documents, category={category}")

    gap_analysis = []

    for doc in docs:
        doc_id = doc["doc_id"]
        filename = doc["filename"]
        raw_text = doc.get("raw_text", "")

        messages.append(f"[gap_analysis] Analysing '{filename}'...")
        logger.info(f"[gap_analysis] Processing {filename}")

        clauses = _split_into_clauses(raw_text)
        logger.info(f"[gap_analysis] {filename}: {len(clauses)} clauses identified")

        doc_gaps = []
        non_compliant_count = 0

        for clause in clauses:
            clause_text = clause["text"]

            # Retrieve legal context via RAG
            legal_context = _build_legal_context(clause_text, category)

            try:
                response_text = call_llm(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=CLAUSE_ANALYSIS_PROMPT.format(
                        source_jurisdiction=source_jurisdiction,
                        policy_category=category,
                        clause_text=clause_text,
                        legal_context=legal_context,
                    ),
                    model=REASONING_MODEL,
                    agent_name="gap_analysis",
                    temperature=0.1,
                )
                result = parse_json_response(response_text)
                gaps = result.get("gaps", [])

                for gap in gaps:
                    gap_entry = {
                        "clause_heading": clause["heading"],
                        "clause_text": clause_text[:500],  # Truncate for storage
                        "is_compliant": gap.get("is_compliant", True),
                        "gap_description": gap.get("gap_description", ""),
                        "relevant_law": gap.get("relevant_law", ""),
                        "required_action": gap.get("required_action", ""),
                        "confidence": gap.get("confidence", 50),
                    }
                    doc_gaps.append(gap_entry)
                    if not gap.get("is_compliant", True):
                        non_compliant_count += 1

            except Exception as e:
                logger.error(f"[gap_analysis] Failed analysing clause '{clause['heading']}' in {filename}: {e}")
                errors.append(f"Gap analysis failed for clause '{clause['heading']}' in {filename}: {str(e)}")
                doc_gaps.append({
                    "clause_heading": clause["heading"],
                    "clause_text": clause_text[:500],
                    "is_compliant": False,
                    "gap_description": f"Analysis failed: {str(e)}",
                    "relevant_law": "Review required",
                    "required_action": "Manual review needed",
                    "confidence": 0,
                })

        doc_report = {
            "doc_id": doc_id,
            "filename": filename,
            "total_clauses_analysed": len(clauses),
            "non_compliant_clauses": non_compliant_count,
            "gaps": doc_gaps,
        }
        gap_analysis.append(doc_report)

        messages.append(
            f"[gap_analysis] '{filename}': {len(clauses)} clauses analysed, "
            f"{non_compliant_count} non-compliant"
        )
        logger.info(f"[gap_analysis] {filename}: {non_compliant_count}/{len(clauses)} non-compliant")

    total_gaps = sum(r["non_compliant_clauses"] for r in gap_analysis)
    messages.append(f"[gap_analysis] Complete — {total_gaps} total compliance gaps found")

    return {
        "gap_analysis": gap_analysis,
        "agent_messages": messages,
        "errors": errors,
    }
