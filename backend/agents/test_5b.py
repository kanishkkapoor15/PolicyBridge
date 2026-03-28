"""Step 5B integration test — runs planning, conversion, chat, and summary agents.

Builds on 5A mock state (ingestion + conflict + gap analysis already done).
Run: cd backend && python -m agents.test_5b
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    # Ensure knowledge base is ingested
    from rag.store import is_knowledge_base_ingested, ingest_knowledge_base
    if not is_knowledge_base_ingested():
        print("Ingesting knowledge base...")
        ingest_knowledge_base()

    # ── Run 5A agents first to build state ──
    print("\n" + "=" * 60)
    print("RUNNING 5A AGENTS (ingestion + conflicts + gap analysis)")
    print("=" * 60)

    from agents.test_5a import LEAVE_POLICY_US, DATA_HANDLING_POLICY_US
    from agents.ingestion_agent import run_ingestion_agent
    from agents.conflict_agent import run_conflict_agent
    from agents.gap_analysis_agent import run_gap_analysis_agent

    state = {
        "session_id": "test-5b",
        "policy_category": "hr_employment",
        "source_jurisdiction": "us_delaware",
        "target_jurisdiction": "ireland_eu",
        "uploaded_documents": [
            {"doc_id": "doc-leave", "filename": "employee_leave_policy.pdf", "raw_text": LEAVE_POLICY_US},
            {"doc_id": "doc-data", "filename": "data_handling_policy.pdf", "raw_text": DATA_HANDLING_POLICY_US},
        ],
        "current_doc_index": 0,
        "intra_batch_conflicts": [],
        "gap_analysis": [],
        "conversion_plan": {},
        "plan_approved": False,
        "converted_documents": [],
        "current_doc_approved": False,
        "final_report": None,
        "outstanding_issues": [],
        "export_ready": False,
        "chat_history": [],
        "current_stage": "ingestion",
        "agent_messages": [],
        "errors": [],
    }

    state.update(run_ingestion_agent(state))
    print(f"  Ingestion done: {[d.get('doc_type') for d in state['uploaded_documents']]}")

    state.update(run_conflict_agent(state))
    print(f"  Conflicts: {len(state['intra_batch_conflicts'])}")

    state.update(run_gap_analysis_agent(state))
    total_gaps = sum(r.get("non_compliant_clauses", 0) for r in state["gap_analysis"])
    print(f"  Gap analysis done: {total_gaps} total gaps")

    # ── Agent 4: PlanningAgent ──
    print("\n" + "=" * 60)
    print("AGENT 4: PlanningAgent")
    print("=" * 60)

    from agents.planning_agent import run_planning_agent
    state.update(run_planning_agent(state))

    plan = state["conversion_plan"]
    print(f"\n  Summary: {plan.get('summary', 'N/A')}")
    print(f"  Risk level: {plan.get('risk_level', 'N/A')}")
    print(f"  Total gaps: {plan.get('total_gaps_found', 0)}")
    print(f"  Estimated changes: {plan.get('estimated_changes', 0)}")
    print(f"  Solicitor items: {len(plan.get('items_requiring_solicitor_review', []))}")

    # Show first doc's planned changes
    actions = plan.get("per_document_actions", [])
    if actions:
        first = actions[0]
        print(f"\n  First document: {first.get('filename', '?')} ({first.get('doc_type', '?')})")
        print(f"  Planned changes ({len(first.get('planned_changes', []))}):")
        for change in first.get("planned_changes", [])[:3]:
            print(f"    [{change.get('change_id', '?')}] {change.get('impact', '?')} impact, {change.get('confidence', 0)}% confidence")
            print(f"      Current: {change.get('current_clause_summary', 'N/A')[:100]}")
            print(f"      Proposed: {change.get('proposed_change_summary', 'N/A')[:100]}")
            print(f"      Legal basis: {change.get('legal_basis', 'N/A')}")

    # ── Approve plan ──
    state["plan_approved"] = True
    state["current_stage"] = "conversion"

    # ── Agent 5: ConversionAgent (Doc 1 - Leave Policy) ──
    print("\n" + "=" * 60)
    print("AGENT 5: ConversionAgent (Document 1: Leave Policy)")
    print("=" * 60)

    from agents.conversion_agent import run_conversion_agent
    state["current_doc_index"] = 0
    state.update(run_conversion_agent(state))

    conv_doc = state["converted_documents"][0]
    print(f"\n  Changes made: {conv_doc.get('total_changes', 0)}")
    print(f"  Solicitor flags: {len(conv_doc.get('flagged_for_solicitor', []))}")

    print(f"\n  First 2 changes:")
    for change in conv_doc.get("changes", [])[:2]:
        print(f"\n    [{change.get('change_id', '?')}] Type: {change.get('change_type', '?')} | Confidence: {change.get('confidence', 0)}%")
        print(f"    ORIGINAL: {change.get('original_clause', '')[:150]}...")
        print(f"    CONVERTED: {change.get('new_clause', '')[:150]}...")
        print(f"    Citation: {change.get('legal_citation', 'N/A')}")
        print(f"    Reason: {change.get('plain_english_reason', 'N/A')[:120]}")

    # ── Agent 6: ChatAgent ──
    print("\n" + "=" * 60)
    print("AGENT 6: ChatAgent")
    print("=" * 60)

    from agents.chat_agent import run_chat_agent
    chat_result = run_chat_agent(state, "Why was the PTO clause changed and is 20 days the absolute minimum?")

    print(f"\n  Question: Why was the PTO clause changed and is 20 days the absolute minimum?")
    print(f"\n  Response: {chat_result.get('response', 'N/A')}")
    if chat_result.get("suggested_actions"):
        print(f"  Suggested actions: {chat_result['suggested_actions']}")
    if chat_result.get("rag_sources_used"):
        print(f"  RAG sources: {chat_result['rag_sources_used']}")

    # ── Approve doc 1, convert doc 2 ──
    state["current_doc_approved"] = True
    state["current_doc_index"] = 1
    state["current_stage"] = "conversion"

    print("\n" + "=" * 60)
    print("AGENT 5: ConversionAgent (Document 2: Data Handling Policy)")
    print("=" * 60)

    state.update(run_conversion_agent(state))

    conv_doc2 = state["converted_documents"][1]
    print(f"\n  Changes made: {conv_doc2.get('total_changes', 0)}")
    print(f"  Solicitor flags: {len(conv_doc2.get('flagged_for_solicitor', []))}")

    # ── Agent 7: SummaryAgent ──
    print("\n" + "=" * 60)
    print("AGENT 7: SummaryAgent")
    print("=" * 60)

    from agents.summary_agent import run_summary_agent
    state.update(run_summary_agent(state))

    report = state["final_report"]
    print(f"\n  Executive Summary: {report.get('executive_summary', 'N/A')}")
    print(f"  Compliance Score: {report.get('compliance_score_before', 0)}% → {report.get('compliance_score_after', 0)}%")
    print(f"  Total gaps: {report.get('total_gaps_identified', 0)}")
    print(f"  Total changes: {report.get('total_changes_made', 0)}")
    print(f"  Changes by framework: {json.dumps(report.get('changes_by_framework', {}), indent=4)}")
    print(f"  Documents summary:")
    for ds in report.get("documents_summary", []):
        print(f"    {ds['filename']}: {ds['gaps_found']} gaps → {ds['changes_made']} changes, {ds['solicitor_items']} solicitor items [{ds['status']}]")
    print(f"  Next steps: {report.get('next_steps', [])}")
    print(f"\n  Outstanding issues: {len(state.get('outstanding_issues', []))}")
    print(f"  Export ready: {state.get('export_ready', False)}")

    # ── Verify export ──
    print("\n" + "=" * 60)
    print("EXPORT TEST")
    print("=" * 60)

    from utils.export import generate_word_export, generate_json_export
    docx_bytes = generate_word_export(state)
    json_str = generate_json_export(state)
    print(f"  Word export: {len(docx_bytes):,} bytes")
    print(f"  JSON export: {len(json_str):,} chars")

    # ── Final assertions ──
    print("\n" + "=" * 60)
    print("VALIDATION")
    print("=" * 60)

    checks = [
        ("Plan has per_document_actions", len(plan.get("per_document_actions", [])) >= 2),
        ("Doc 1 has real changes", conv_doc.get("total_changes", 0) >= 3),
        ("Doc 2 has real changes", conv_doc2.get("total_changes", 0) >= 3),
        ("Changes have legal citations", all(c.get("legal_citation") for c in conv_doc.get("changes", [])[:3])),
        ("Chat agent responded", len(chat_result.get("response", "")) > 50),
        ("Compliance score after > before", report.get("compliance_score_after", 0) > report.get("compliance_score_before", 0)),
        ("Export ready", state.get("export_ready") is True),
        ("Word export generated", len(docx_bytes) > 1000),
    ]

    all_passed = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {name}")

    print("\n" + "=" * 60)
    print(f"TEST {'PASSED' if all_passed else 'FAILED'}")
    print("=" * 60)

    if state["errors"]:
        print(f"\nErrors encountered: {len(state['errors'])}")
        for e in state["errors"]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
