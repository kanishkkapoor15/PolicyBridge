"""DocumentIngestionAgent — reads uploaded files, extracts clean text, identifies document type."""

import logging

from agents.llm_client import call_llm, parse_json_response
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a legal document classifier specialising in corporate policy documents.
Your job is to analyse policy documents and extract structured metadata.
Always respond with valid JSON only. No explanations, no markdown, no preamble."""

USER_PROMPT_TEMPLATE = """Analyse this corporate policy document and return a JSON object with:
{{
  "doc_type": "the type of policy document (e.g. Employee Handbook, Leave Policy, Acceptable Use Policy, Data Retention Policy, Anti-Harassment Policy, etc.)",
  "jurisdiction_signals": ["list of any explicit mentions of US states, UK law, or specific regulations that indicate origin jurisdiction"],
  "key_sections": ["list of major section headings found in the document"],
  "estimated_clause_count": <integer — rough count of distinct policy clauses or rules>
}}

Document filename: {filename}
Document text:
---
{text}
---

Respond with the JSON object only."""


def run_ingestion_agent(state: dict) -> dict:
    """Process uploaded documents: classify type and extract metadata."""
    docs = state.get("uploaded_documents", [])
    messages = list(state.get("agent_messages", []))
    errors = list(state.get("errors", []))

    messages.append(f"[ingestion] Starting document classification for {len(docs)} documents")
    logger.info(f"[ingestion] Processing {len(docs)} documents")

    updated_docs = []
    for doc in docs:
        doc_id = doc["doc_id"]
        filename = doc["filename"]
        raw_text = doc.get("raw_text", "")

        # Truncate very long documents for classification (first 3000 chars is enough)
        text_for_classification = raw_text[:3000] if len(raw_text) > 3000 else raw_text

        try:
            response_text = call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=USER_PROMPT_TEMPLATE.format(filename=filename, text=text_for_classification),
                model=CHAT_MODEL,
                agent_name="ingestion",
            )
            metadata = parse_json_response(response_text)

            updated_doc = {
                **doc,
                "doc_type": metadata.get("doc_type", "Unknown"),
                "jurisdiction_signals": metadata.get("jurisdiction_signals", []),
                "key_sections": metadata.get("key_sections", []),
                "estimated_clause_count": metadata.get("estimated_clause_count", 0),
            }
            messages.append(f"[ingestion] Classified '{filename}' as '{updated_doc['doc_type']}'")
            logger.info(f"[ingestion] {filename} → {updated_doc['doc_type']}")

        except Exception as e:
            logger.error(f"[ingestion] Failed to classify {filename}: {e}")
            errors.append(f"Ingestion failed for {filename}: {str(e)}")
            updated_doc = {
                **doc,
                "doc_type": "Unknown",
                "jurisdiction_signals": [],
                "key_sections": [],
                "estimated_clause_count": 0,
            }
            messages.append(f"[ingestion] Failed to classify '{filename}', marked as Unknown")

        updated_docs.append(updated_doc)

    messages.append(f"[ingestion] Complete — {len(updated_docs)} documents classified")

    return {
        "uploaded_documents": updated_docs,
        "current_stage": "analysis",
        "agent_messages": messages,
        "errors": errors,
    }
