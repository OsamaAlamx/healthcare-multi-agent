"""
Agent evaluation runner.

Usage (from src/):
    python evaluation/run_evaluation.py              # all suites
    python evaluation/run_evaluation.py --skip-e2e  # deterministic suites only
    python evaluation/run_evaluation.py --suite triage

Results are printed to the console, written to
evaluation/evaluation_report.md, and recorded in the evaluation_runs table.
"""
import argparse
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from database import init_db, get_db
from models import Patient, MedicalRecord, EvaluationRun
from auth import register_patient
from agent_router import classify_intent, handle_patient_query
from memory.conversation_memory import clear_conversation
from mcp_servers.clinical_server import clinical_triage
from guardrails.input_guardrails import apply_input_guardrails
from guardrails.output_guardrails import apply_output_guardrails, PRESCRIBER_BLOCKED_RESPONSE
from rag.vector_store import DRUG_COLLECTION, RECORDS_COLLECTION, search_collection
from rag.build_rag_indexes import ensure_indexes
from evaluation.test_cases import (
    TRIAGE_CASES, ROUTER_CASES, GUARDRAIL_INPUT_CASES, GUARDRAIL_OUTPUT_CASES,
    RAG_DRUG_CASES, RAG_RECORD_CASES, E2E_CASES,
)
from evaluation.evaluators import contains_any, contains_none, llm_judge

EVAL_PATIENT_EMAIL = "eval.patient@system.local"
EVAL_PATIENT_NAME = "Eval Patient"
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_report.md")


def _ensure_eval_patient() -> dict:
    register_patient(EVAL_PATIENT_NAME, EVAL_PATIENT_EMAIL, "EvalPass123")
    with get_db() as db:
        patient = db.query(Patient).filter(Patient.email == EVAL_PATIENT_EMAIL).first()
        return {"patient_id": patient.patient_id, "name": patient.name, "email": patient.email}


def _seed_eval_records(patient: dict):
    with get_db() as db:
        existing = db.query(MedicalRecord).filter(
            MedicalRecord.patient_email == patient["email"]
        ).count()
    if existing:
        return
    with get_db() as db:
        db.add(MedicalRecord(
            patient_id=patient["patient_id"], patient_email=patient["email"],
            record_type="allergy",
            details="Penicillin allergy — rash and facial swelling", is_active=True,
        ))
        db.add(MedicalRecord(
            patient_id=patient["patient_id"], patient_email=patient["email"],
            record_type="chronic_condition",
            details="Type 2 diabetes, controlled with metformin 500 mg twice daily", is_active=True,
        ))


def run_triage_suite() -> list:
    results = []
    for case in TRIAGE_CASES:
        output = clinical_triage(case["input"])
        passed = case["expect_contains"] in output
        results.append({
            "name": case["name"], "passed": passed,
            "detail": "" if passed else output.split("\n")[0],
        })
    return results


def run_router_suite() -> list:
    results = []
    for case in ROUTER_CASES:
        try:
            intent = classify_intent(case["message"])
            passed = intent == case["expected"]
            detail = "" if passed else f"expected {case['expected']}, got {intent}"
        except Exception as e:
            passed, detail = False, f"error: {e}"
        results.append({"name": case["name"], "passed": passed, "detail": detail})
    return results


def run_guardrail_suite() -> list:
    results = []
    for case in GUARDRAIL_INPUT_CASES:
        outcome = apply_input_guardrails(case["message"], patient_id="EVAL")
        if case["expect"] == "blocked":
            passed = outcome["allowed"] is False
        elif case["expect"] == "redacted":
            passed = outcome["allowed"] and "[REDACTED]" in outcome["message"]
        elif case["expect"] == "flagged":
            passed = outcome["allowed"] and outcome["flags"]["emergency"]
        else:
            passed = (outcome["allowed"]
                      and "[REDACTED]" not in outcome["message"]
                      and not outcome["flags"]["emergency"])
        results.append({"name": case["name"], "passed": passed, "detail": ""})

    for case in GUARDRAIL_OUTPUT_CASES:
        outcome = apply_output_guardrails(
            case["response"], case["agent"],
            patient_email=case.get("patient_email"),
            emergency_input=case.get("emergency", False),
            patient_id="EVAL",
        )
        response = outcome["response"]
        if case["expect"] == "blocked":
            passed = response == PRESCRIBER_BLOCKED_RESPONSE
        elif case["expect"] == "masked":
            passed = "***@***.***" in response
        elif case["expect"] == "emergency_appended":
            passed = "seek emergency medical care" in response
        else:
            passed = response == case["response"]
        results.append({"name": case["name"], "passed": passed, "detail": ""})
    return results


def run_rag_suite(patient_id: str) -> list:
    results = []
    for case in RAG_DRUG_CASES:
        hits = search_collection(DRUG_COLLECTION, case["query"], n_results=3)
        text = " ".join(hit["document"] for hit in hits)
        passed = contains_any(text, case["expect_any"])
        results.append({
            "name": case["name"], "passed": passed,
            "detail": "" if passed else "expected drug not in top matches",
        })
    for case in RAG_RECORD_CASES:
        hits = search_collection(
            RECORDS_COLLECTION, case["query"], n_results=5,
            where={"patient_id": patient_id},
        )
        text = " ".join(hit["document"] for hit in hits)
        passed = contains_any(text, case["expect_any"])
        results.append({
            "name": case["name"], "passed": passed,
            "detail": "" if passed else "expected record not retrieved",
        })
    return results


def run_e2e_suite(patient: dict) -> list:
    results = []
    for case in E2E_CASES:
        start = time.time()
        try:
            # Each E2E case must start with a clean conversation — leftover
            # history from the previous case (e.g. an unanswered headache
            # question) contaminates the agent's context and skews results.
            clear_conversation(patient["patient_id"])
            outcome = handle_patient_query(
                patient["patient_id"], patient["name"], patient["email"], case["message"]
            )
            response = outcome["response"]
            passed = (contains_any(response, case["expect_any"])
                      and contains_none(response, case["not_any"]))
            judge = llm_judge(case["message"], response)
            if not judge["passed"]:
                passed = False
            detail = "" if passed else f"response: {response[:200]}"
        except Exception as e:
            passed, detail = False, f"error: {e}"
        results.append({
            "name": case["name"], "passed": passed, "detail": detail,
            "latency": round(time.time() - start, 1),
        })
    return results


def _print_suite(name: str, results: list):
    passed = sum(1 for r in results if r["passed"])
    print(f"\n{'=' * 60}")
    print(f"SUITE: {name}  —  {passed}/{len(results)} passed")
    print("=" * 60)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['name']}")
        if not r["passed"] and r["detail"]:
            print(f"        {r['detail']}")


def _write_report(suite_results: dict, duration: float):
    total = sum(len(r) for r in suite_results.values())
    passed = sum(1 for results in suite_results.values() for r in results if r["passed"])
    lines = [
        "# Agent Evaluation Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Overall: {passed}/{total} passed ({(passed / total * 100) if total else 0:.0f}%)",
        f"Total duration: {duration:.1f}s",
        "",
    ]
    for name, results in suite_results.items():
        suite_passed = sum(1 for r in results if r["passed"])
        rate = (suite_passed / len(results) * 100) if results else 0
        lines.append(f"## {name} — {suite_passed}/{len(results)} ({rate:.0f}%)")
        lines.append("")
        for r in results:
            lines.append(f"- {'✅' if r['passed'] else '❌'} {r['name']}")
            if not r["passed"] and r["detail"]:
                lines.append(f"  - {r['detail']}")
        lines.append("")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return total, passed


def _persist_runs(suite_results: dict, duration: float):
    for name, results in suite_results.items():
        suite_passed = sum(1 for r in results if r["passed"])
        with get_db() as db:
            db.add(EvaluationRun(
                suite=name,
                total_cases=len(results),
                passed=suite_passed,
                failed=len(results) - suite_passed,
                pass_rate=(suite_passed / len(results)) if results else 0.0,
                duration_seconds=round(duration, 2),
                report_path=REPORT_PATH,
            ))


def main():
    parser = argparse.ArgumentParser(description="Agent evaluation runner")
    parser.add_argument("--suite", default="all",
                        choices=["all", "fast", "triage", "router", "guardrails", "rag", "e2e"])
    parser.add_argument("--skip-e2e", action="store_true",
                        help="run deterministic suites only")
    args = parser.parse_args()

    init_db()
    patient = _ensure_eval_patient()
    _seed_eval_records(patient)
    ensure_indexes()

    selection = "fast" if (args.skip_e2e and args.suite == "all") else args.suite

    start = time.time()
    suite_results = {}

    if selection in ("all", "fast", "triage"):
        suite_results["triage"] = run_triage_suite()
    if selection in ("all", "fast", "guardrails"):
        suite_results["guardrails"] = run_guardrail_suite()
    if selection in ("all", "fast", "rag"):
        suite_results["rag"] = run_rag_suite(patient["patient_id"])
    if selection in ("all", "router"):
        suite_results["router"] = run_router_suite()
    if selection in ("all", "e2e"):
        suite_results["e2e"] = run_e2e_suite(patient)

    duration = time.time() - start

    for name, results in suite_results.items():
        _print_suite(name, results)

    total, passed = _write_report(suite_results, duration)
    _persist_runs(suite_results, duration)

    print(f"\nReport saved to: {REPORT_PATH}")
    print(f"Overall: {passed}/{total} passed in {duration:.1f}s")


if __name__ == "__main__":
    main()