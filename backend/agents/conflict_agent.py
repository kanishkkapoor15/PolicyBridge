"""ConflictDetectionAgent — cross-references all docs in the batch, flags contradictions."""

import logging
from itertools import combinations

from agents.llm_client import call_llm, parse_json_response
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a legal document analyst specialising in identifying contradictions between corporate policy documents.
Your job is to compare two policy documents and identify genuine conflicts — contradictory rules, inconsistent definitions, or overlapping scope with different requirements.
Only flag real conflicts, not merely similar topics or minor wording differences.
Always respond with valid JSON only. No explanations, no markdown, no preamble."""

USER_PROMPT_TEMPLATE = """Compare these two policy documents and identify any genuine conflicts or contradictions.

Return a JSON object:
{{
  "conflicts": [
    {{
      "doc_a_excerpt": "the specific text from Document A that conflicts",
      "doc_b_excerpt": "the specific text from Document B that conflicts",
      "conflict_description": "clear description of the contradiction",
      "severity": "low|medium|high"
    }}
  ]
}}

If no genuine conflicts exist, return: {{"conflicts": []}}

Document A: "{doc_a_name}" (Type: {doc_a_type})
---
{doc_a_text}
---

Document B: "{doc_b_name}" (Type: {doc_b_type})
---
{doc_b_text}
---

Respond with the JSON object only."""

MAX_PAIRS_FULL_SCAN = 15  # C(6,2) = 15 — cap for full pairwise comparison


def _get_comparison_pairs(docs: list[dict]) -> list[tuple[dict, dict]]:
    """Get document pairs to compare. Limits pairs for large batches."""
    if len(docs) <= 6:
        return list(combinations(docs, 2))

    # For large batches, only compare documents of the same type + adjacent pairs
    logger.warning(f"[conflicts] {len(docs)} documents — using limited pairwise comparison")
    pairs = set()

    # Same doc_type pairs
    by_type: dict[str, list[dict]] = {}
    for doc in docs:
        dt = doc.get("doc_type", "Unknown")
        by_type.setdefault(dt, []).append(doc)
    for group in by_type.values():
        for pair in combinations(group, 2):
            pairs.add((pair[0]["doc_id"], pair[1]["doc_id"]))

    # Adjacent pairs
    for i in range(len(docs) - 1):
        pairs.add((docs[i]["doc_id"], docs[i + 1]["doc_id"]))

    # Resolve back to doc dicts
    doc_map = {d["doc_id"]: d for d in docs}
    return [(doc_map[a], doc_map[b]) for a, b in pairs]


def run_conflict_agent(state: dict) -> dict:
    """Detect conflicts between documents in the batch."""
    docs = state.get("uploaded_documents", [])
    messages = list(state.get("agent_messages", []))
    errors = list(state.get("errors", []))

    if len(docs) < 2:
        messages.append("[conflicts] Only 1 document — skipping conflict detection")
        return {
            "intra_batch_conflicts": [],
            "agent_messages": messages,
            "errors": errors,
        }

    pairs = _get_comparison_pairs(docs)
    messages.append(f"[conflicts] Comparing {len(pairs)} document pairs")
    logger.info(f"[conflicts] Comparing {len(pairs)} pairs from {len(docs)} documents")

    all_conflicts = []

    for doc_a, doc_b in pairs:
        # Truncate texts for comparison
        text_a = doc_a.get("raw_text", "")[:2500]
        text_b = doc_b.get("raw_text", "")[:2500]

        try:
            response_text = call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=USER_PROMPT_TEMPLATE.format(
                    doc_a_name=doc_a["filename"],
                    doc_a_type=doc_a.get("doc_type", "Unknown"),
                    doc_a_text=text_a,
                    doc_b_name=doc_b["filename"],
                    doc_b_type=doc_b.get("doc_type", "Unknown"),
                    doc_b_text=text_b,
                ),
                model=CHAT_MODEL,
                agent_name="conflicts",
            )
            result = parse_json_response(response_text)
            conflicts = result.get("conflicts", [])

            for conflict in conflicts:
                all_conflicts.append({
                    "doc_a_id": doc_a["doc_id"],
                    "doc_b_id": doc_b["doc_id"],
                    "doc_a_name": doc_a["filename"],
                    "doc_b_name": doc_b["filename"],
                    "doc_a_excerpt": conflict.get("doc_a_excerpt", ""),
                    "doc_b_excerpt": conflict.get("doc_b_excerpt", ""),
                    "conflict_description": conflict.get("conflict_description", ""),
                    "severity": conflict.get("severity", "low"),
                })

        except Exception as e:
            logger.error(f"[conflicts] Failed comparing {doc_a['filename']} vs {doc_b['filename']}: {e}")
            errors.append(f"Conflict detection failed for {doc_a['filename']} vs {doc_b['filename']}: {str(e)}")

    messages.append(f"[conflicts] Found {len(all_conflicts)} conflict(s) across {len(pairs)} pairs")
    logger.info(f"[conflicts] Found {len(all_conflicts)} conflicts")

    return {
        "intra_batch_conflicts": all_conflicts,
        "agent_messages": messages,
        "errors": errors,
    }
