"""Step 5A integration test — runs ingestion, conflict detection, and gap analysis agents.

Run: cd backend && python -m agents.test_5a
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Mock policy documents ──────────────────────────────────────────────────

LEAVE_POLICY_US = """
EMPLOYEE LEAVE POLICY
Acme Corp — Delaware, United States
Effective Date: January 1, 2024

1. EMPLOYMENT AT WILL
All employment at Acme Corp is "at will." This means that either the employee or the Company
may terminate the employment relationship at any time, for any reason, with or without cause or
notice. Nothing in this policy creates a contract of employment or guarantees employment for any
specific duration.

2. PAID TIME OFF (PTO)
Full-time employees are eligible for 10 days of paid time off per year after completing a 90-day
probationary period. PTO accrues on a monthly basis at a rate of 0.83 days per month. Unused PTO
does not carry over to the next calendar year — all unused PTO is forfeited on December 31 ("use it
or lose it" policy).

3. FAMILY AND MEDICAL LEAVE (FMLA)
Eligible employees (12+ months of service, 1,250+ hours worked) may take up to 12 weeks of
unpaid leave per year under the Family and Medical Leave Act for: birth/adoption of a child,
serious health condition of the employee or immediate family member, or qualifying military
exigency. Employees must provide 30 days advance notice when foreseeable.

4. SICK LEAVE
Employees receive 3 paid sick days per year. Unused sick days are not paid out upon termination.
A doctor's note is required for absences exceeding 2 consecutive days.

5. PUBLIC HOLIDAYS
The Company observes the following federal holidays: New Year's Day, Martin Luther King Jr. Day,
Presidents' Day, Memorial Day, Independence Day (July 4), Labor Day, Columbus Day, Veterans Day,
Thanksgiving, Christmas Day. Employees required to work on a holiday receive 1.5x overtime pay.

6. OVERTIME
Non-exempt employees are entitled to overtime pay at 1.5 times the regular rate for hours worked
in excess of 40 hours per week, in compliance with the Fair Labor Standards Act (FLSA). Exempt
employees are not eligible for overtime pay. All overtime must be pre-approved by a supervisor.

7. BEREAVEMENT LEAVE
Employees are granted up to 3 days of paid bereavement leave for the death of an immediate family
member (spouse, child, parent, sibling).

8. JURY DUTY
Employees will receive their regular pay for up to 5 days of jury duty per year.
"""

DATA_HANDLING_POLICY_US = """
DATA HANDLING AND PRIVACY POLICY
Acme Corp — Delaware, United States
Effective Date: March 1, 2024

1. SCOPE
This policy governs the collection, storage, processing, and disposal of personal information by
Acme Corp and applies to all employees, contractors, and third-party vendors with access to company
data systems.

2. DATA COLLECTION
The Company collects personal information from employees and customers as necessary for business
operations. Types of data collected include: name, address, Social Security Number (SSN), date of
birth, employment history, salary information, bank details for payroll, health insurance data,
and performance evaluations. Data is collected with implied consent through the employment
relationship. No separate consent form is required.

3. DATA STORAGE AND RETENTION
All personal data is stored on Company servers located in our Delaware data centre and AWS US-East
region. Data is retained indefinitely unless the individual requests deletion. Employee records are
retained for the duration of employment plus 3 years. Customer data is retained for the lifetime
of the customer relationship plus 5 years for tax and audit purposes.

4. EMPLOYEE MONITORING
The Company reserves the right to monitor all employee activity on company-owned devices and
networks, including email, internet browsing, instant messaging, file transfers, and phone calls.
By using company equipment, employees consent to this monitoring. No prior notice is required
before initiating monitoring of a specific employee.

5. DATA SHARING
Personal data may be shared with third-party vendors for HR administration, payroll processing,
benefits management, and marketing analytics. Vendors are selected based on cost-effectiveness and
operational needs. Data may be transferred to any country where the Company or its vendors operate
without restriction.

6. BACKGROUND CHECKS
All prospective employees must undergo a comprehensive background check including criminal history
(felony and misdemeanor), credit history, driving record, social media review, and reference
verification. Candidates who refuse a background check will not be considered for employment.

7. BREACH NOTIFICATION
In the event of a data breach, the Company will assess the situation within 30 days and notify
affected individuals if the Company determines notification is appropriate. Notification to state
attorneys general will follow applicable state breach notification laws (e.g., Delaware Code Title 6,
Chapter 12B). There is no fixed timeline for notification.

8. CALIFORNIA RESIDENTS (CCPA COMPLIANCE)
Residents of California have additional rights under the California Consumer Privacy Act (CCPA),
including the right to know what personal information is collected, the right to delete personal
information, and the right to opt out of the sale of personal information.

9. DATA DISPOSAL
When data is no longer needed, it will be securely deleted using industry-standard methods.
Physical documents will be shredded. Electronic data will be overwritten or degaussed.
"""

# ── Test runner ────────────────────────────────────────────────────────────


def main():
    # Ensure knowledge base is ingested
    from rag.store import is_knowledge_base_ingested, ingest_knowledge_base
    if not is_knowledge_base_ingested():
        print("Ingesting knowledge base...")
        ingest_knowledge_base()

    from agents.ingestion_agent import run_ingestion_agent
    from agents.conflict_agent import run_conflict_agent
    from agents.gap_analysis_agent import run_gap_analysis_agent

    state = {
        "session_id": "test-5a",
        "policy_category": "hr_employment",
        "source_jurisdiction": "us_delaware",
        "target_jurisdiction": "ireland_eu",
        "uploaded_documents": [
            {
                "doc_id": "doc-leave",
                "filename": "employee_leave_policy.pdf",
                "raw_text": LEAVE_POLICY_US,
            },
            {
                "doc_id": "doc-data",
                "filename": "data_handling_policy.pdf",
                "raw_text": DATA_HANDLING_POLICY_US,
            },
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

    # ── Agent 1: Ingestion ──
    print("\n" + "=" * 60)
    print("AGENT 1: DocumentIngestionAgent")
    print("=" * 60)
    state.update(run_ingestion_agent(state))

    for doc in state["uploaded_documents"]:
        print(f"\n  Document: {doc['filename']}")
        print(f"    Type: {doc.get('doc_type', 'N/A')}")
        print(f"    Jurisdiction signals: {doc.get('jurisdiction_signals', [])}")
        print(f"    Key sections: {doc.get('key_sections', [])}")
        print(f"    Est. clause count: {doc.get('estimated_clause_count', 0)}")

    # ── Agent 2: Conflict Detection ──
    print("\n" + "=" * 60)
    print("AGENT 2: ConflictDetectionAgent")
    print("=" * 60)
    state.update(run_conflict_agent(state))

    conflicts = state.get("intra_batch_conflicts", [])
    print(f"\n  Conflicts found: {len(conflicts)}")
    for c in conflicts:
        print(f"\n  [{c['severity'].upper()}] {c['doc_a_name']} vs {c['doc_b_name']}")
        print(f"    {c['conflict_description']}")

    # ── Agent 3: Gap Analysis ──
    print("\n" + "=" * 60)
    print("AGENT 3: GapAnalysisAgent")
    print("=" * 60)
    state.update(run_gap_analysis_agent(state))

    for doc_report in state.get("gap_analysis", []):
        print(f"\n  Document: {doc_report['filename']}")
        print(f"    Clauses analysed: {doc_report['total_clauses_analysed']}")
        print(f"    Non-compliant: {doc_report['non_compliant_clauses']}")

        # Show top gaps by confidence (non-compliant only)
        non_compliant_gaps = [g for g in doc_report["gaps"] if not g.get("is_compliant", True)]
        sorted_gaps = sorted(non_compliant_gaps, key=lambda x: x.get("confidence", 0), reverse=True)

        print(f"    Top gaps (by confidence):")
        for gap in sorted_gaps[:5]:
            print(f"\n      [{gap['confidence']}%] {gap['clause_heading']}")
            print(f"        Gap: {gap['gap_description'][:120]}")
            print(f"        Law: {gap['relevant_law']}")
            print(f"        Action: {gap['required_action'][:120]}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("ERRORS")
    print("=" * 60)
    if state["errors"]:
        for e in state["errors"]:
            print(f"  {e}")
    else:
        print("  None")

    print("\n" + "=" * 60)
    print("AGENT MESSAGES LOG")
    print("=" * 60)
    for msg in state["agent_messages"]:
        print(f"  {msg}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
