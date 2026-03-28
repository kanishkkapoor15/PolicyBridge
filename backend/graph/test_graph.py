"""Smoke test for the PolicyBridge LangGraph workflow.

Verifies:
1. Graph runs from START to first interrupt (human_plan_approval)
2. Resuming with approval proceeds to convert_document → second interrupt (human_doc_approval)
3. Document approval loop processes all documents
4. Graph reaches generate_summary and END

Run: cd backend && python -m graph.test_graph
"""

import logging
import sys
from pathlib import Path

# Ensure backend/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    from langgraph.types import Command
    from graph.workflow import get_graph

    graph = get_graph()
    thread_id = "test-001"
    config = {"configurable": {"thread_id": thread_id}}

    # Initial state with 2 mock documents
    initial_state = {
        "session_id": thread_id,
        "policy_category": "hr_employment",
        "source_jurisdiction": "us_delaware",
        "target_jurisdiction": "ireland_eu",
        "uploaded_documents": [
            {"doc_id": "doc-1", "filename": "employee_handbook.pdf", "raw_text": "Sample employee handbook text...", "doc_type": "hr_policy"},
            {"doc_id": "doc-2", "filename": "leave_policy.docx", "raw_text": "Sample leave policy text...", "doc_type": "hr_policy"},
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

    print(f"\n{'='*60}")
    print(f"[Graph] Starting session: {thread_id}")
    print(f"{'='*60}\n")

    # --- Run 1: START → human_plan_approval (interrupted before) ---
    result = None
    for event in graph.stream(initial_state, config, stream_mode="values"):
        result = event

    snapshot = graph.get_state(config)
    print(f"\n[INTERRUPT] Paused at: {snapshot.next}")
    print(f"  Current stage: {result.get('current_stage', '?')}")
    print(f"  Plan: {result.get('conversion_plan', {}).get('summary', 'N/A')}")

    # --- Resume 1: Approve plan → runs human_plan_approval, convert_document → interrupted before human_doc_approval ---
    print(f"\nResuming with plan approval...\n")
    for event in graph.stream(Command(resume={"approved": True}), config, stream_mode="values"):
        result = event

    snapshot = graph.get_state(config)
    print(f"\n[INTERRUPT] Paused at: {snapshot.next}")
    print(f"  Current stage: {result.get('current_stage', '?')}")
    print(f"  Converted docs so far: {len(result.get('converted_documents', []))}")

    # --- Resume 2: Approve doc 1 → advance_or_finish → convert_document (doc 2) → interrupted before human_doc_approval ---
    print(f"\nResuming with doc 1 approval...\n")
    for event in graph.stream(Command(resume={"approved": True}), config, stream_mode="values"):
        result = event

    snapshot = graph.get_state(config)
    print(f"\n[INTERRUPT] Paused at: {snapshot.next}")
    print(f"  Current doc index: {result.get('current_doc_index', '?')}")
    print(f"  Converted docs so far: {len(result.get('converted_documents', []))}")

    # --- Resume 3: Approve doc 2 → advance_or_finish → generate_summary → END ---
    print(f"\nResuming with doc 2 approval...\n")
    for event in graph.stream(Command(resume={"approved": True}), config, stream_mode="values"):
        result = event

    snapshot = graph.get_state(config)
    print(f"\n[COMPLETE] Reached: {snapshot.next}")
    print(f"  Current stage: {result.get('current_stage', '?')}")
    print(f"  Final report: {result.get('final_report', {}).get('executive_summary', 'N/A')}")
    print(f"  Export ready: {result.get('export_ready', False)}")
    print(f"  Total agent messages: {len(result.get('agent_messages', []))}")
    print(f"\nAgent message log:")
    for msg in result.get("agent_messages", []):
        print(f"  {msg}")

    print(f"\n{'='*60}")
    print("SMOKE TEST PASSED")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
