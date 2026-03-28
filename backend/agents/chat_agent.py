"""ChatAgent — stateful chat aware of full session context."""

import logging

from agents.llm_client import call_llm, parse_json_response
from config import CHAT_MODEL
from rag.retrieval import retrieve_relevant_law

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are PolicyBridge, an AI compliance assistant helping an auditor migrate
corporate policies to Irish and EU law compliance.

You have full access to the current session context provided. Answer questions
accurately and cite specific laws when relevant. Be conversational but precise.

Important boundaries:
- You assist with understanding compliance requirements and the conversion process
- You do not provide final legal advice — always note when a solicitor should be consulted
- If asked to make a change to a converted document, acknowledge the request and
  note it will be applied in the next revision pass
- Never fabricate legal citations — if uncertain, say so and suggest verification

Respond with JSON only:
{{"response": "<your answer>", "suggested_actions": ["optional list of next steps"], "rag_sources_used": ["list of legal sources referenced"]}}"""


def _summarise_gaps(gap_analysis: list[dict]) -> str:
    parts = []
    for report in gap_analysis:
        nc = report.get("non_compliant_clauses", 0)
        total = report.get("total_clauses_analysed", 0)
        parts.append(f"{report.get('filename', '?')}: {nc}/{total} non-compliant")
    return "; ".join(parts) if parts else "No gap analysis yet"


def _summarise_changes(converted_documents: list[dict]) -> str:
    parts = []
    for doc in converted_documents:
        parts.append(f"{doc.get('filename', '?')}: {doc.get('total_changes', 0)} changes, {len(doc.get('flagged_for_solicitor', []))} solicitor flags")
    return "; ".join(parts) if parts else "No conversions yet"


def _get_solicitor_flags(state: dict) -> list[dict]:
    flags = []
    for doc in state.get("converted_documents", []):
        for f in doc.get("flagged_for_solicitor", []):
            flags.append({**f, "filename": doc.get("filename", "")})
    return flags


def _build_session_context(state: dict) -> str:
    docs = state.get("uploaded_documents", [])
    filenames = [d.get("filename", "?") for d in docs]
    solicitor_flags = _get_solicitor_flags(state)

    context = f"""SESSION CONTEXT:
- Policy Category: {state.get('policy_category', 'unknown')}
- Source Jurisdiction: {state.get('source_jurisdiction', 'unknown')}
- Target Jurisdiction: Ireland / EU
- Current Stage: {state.get('current_stage', 'unknown')}
- Documents in batch: {filenames}
- Gap analysis: {_summarise_gaps(state.get('gap_analysis', []))}
- Conversion plan status: {'Approved' if state.get('plan_approved') else 'Pending approval'}
- Documents converted: {_summarise_changes(state.get('converted_documents', []))}
- Converted {len(state.get('converted_documents', []))}/{len(docs)} documents
- Solicitor flags: {len(solicitor_flags)} items pending"""

    # Add detail about gaps if available
    gap_analysis = state.get("gap_analysis", [])
    if gap_analysis:
        context += "\n\nGAP DETAILS:"
        for report in gap_analysis:
            for gap in report.get("gaps", []):
                if not gap.get("is_compliant", True):
                    context += f"\n  - [{gap.get('confidence', 0)}%] {report.get('filename', '?')} / {gap.get('clause_heading', '?')}: {gap.get('gap_description', '')[:150]} (Law: {gap.get('relevant_law', 'N/A')})"

    # Add detail about changes if available
    converted = state.get("converted_documents", [])
    if converted:
        context += "\n\nCHANGES MADE:"
        for doc in converted:
            for change in doc.get("changes", [])[:5]:
                context += f"\n  - [{change.get('change_id', '?')}] {change.get('plain_english_reason', '')[:120]} (Law: {change.get('legal_citation', 'N/A')})"

    return context


def run_chat_agent(state: dict, user_message: str) -> dict:
    """Handle a chat message from the auditor with full session awareness."""
    messages = list(state.get("agent_messages", []))
    errors = list(state.get("errors", []))

    session_context = _build_session_context(state)

    # Check if the question might benefit from RAG retrieval
    rag_context = ""
    rag_sources = []
    legal_keywords = ["gdpr", "article", "section", "act", "directive", "regulation",
                      "law", "legal", "compliant", "compliance", "minimum", "required",
                      "statutory", "mandatory"]
    if any(kw in user_message.lower() for kw in legal_keywords):
        results = retrieve_relevant_law(user_message, top_k=3)
        if results:
            rag_parts = []
            for r in results:
                rag_parts.append(f"[{r.source_framework} — {r.section_title}]\n{r.chunk_text[:500]}")
                rag_sources.append(f"{r.source_framework}: {r.section_title}")
            rag_context = "\n\nRELEVANT LEGAL CONTEXT FROM KNOWLEDGE BASE:\n" + "\n---\n".join(rag_parts)

    user_prompt = f"""{session_context}
{rag_context}

AUDITOR'S QUESTION:
{user_message}

Answer the question using the session context and legal knowledge above. Be helpful and specific."""

    try:
        response_text = call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=CHAT_MODEL,
            agent_name="chat",
        )

        try:
            result = parse_json_response(response_text)
            response = result.get("response", response_text)
            suggested_actions = result.get("suggested_actions", [])
            sources = result.get("rag_sources_used", rag_sources)
        except (ValueError, KeyError):
            response = response_text
            suggested_actions = []
            sources = rag_sources

    except Exception as e:
        logger.error(f"[chat] Failed: {e}")
        errors.append(f"Chat agent failed: {str(e)}")
        response = "I'm sorry, I encountered an error processing your question. Please try again."
        suggested_actions = []
        sources = []

    return {
        "response": response,
        "suggested_actions": suggested_actions,
        "rag_sources_used": sources,
    }
