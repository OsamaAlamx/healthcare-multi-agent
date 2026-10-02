"""
MCP Server 3: Clinical Analysis
Handles: symptom triage, document summarization
"""
import sys
import time as _t
_T0 = _t.perf_counter()
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("clinical-server")


@mcp.tool()
def clinical_triage(symptoms: str) -> str:
    """
    Maps symptoms to diagnoses and clinical risk level.
    Returns CRITICAL, HIGH, or LOW with possible conditions and advice.
    """
    text = symptoms.lower()

    critical_triggers = [
        ("chest pain" in text,
 "Myocardial infarction (heart attack), Acute coronary syndrome",
 "Seek emergency medical help immediately."),
        ("shortness of breath" in text,
         "Pulmonary embolism, Asthma attack",
         "Immediate emergency evaluation required."),
        ("sudden weakness" in text or "one side weakness" in text,
         "Stroke (CVA), TIA",
         "Call emergency services immediately."),
        ("slurred speech" in text,
         "Stroke, Neurological emergency",
         "Immediate hospital evaluation required."),
        ("loss of consciousness" in text or "unconscious" in text,
         "Cardiac arrest, Seizure",
         "Emergency medical intervention required."),
        ("vomiting blood" in text,
         "Upper gastrointestinal bleed",
         "Emergency hospital admission required."),
        ("severe headache" in text and "sudden" in text,
         "Brain hemorrhage",
         "Immediate CT scan and emergency care required."),
        ("anaphylaxis" in text or "severe allergic reaction" in text,
         "Anaphylactic shock",
         "Administer emergency treatment immediately."),
        ("high fever" in text and "stiff neck" in text,
         "Meningitis",
         "Immediate hospital admission required."),
    ]

    for condition, diagnosis, advice in critical_triggers:
        if condition:
            return (
                f"RISK LEVEL: CRITICAL\n"
                f"POSSIBLE CONDITIONS: {diagnosis}\n"
                f"ADVICE: {advice}"
            )

    high_triggers = [
        ("seizure" in text, "Epilepsy, Brain injury", "Urgent neurological evaluation."),
        ("severe abdominal pain" in text, "Appendicitis, Pancreatitis", "Urgent surgical evaluation."),
        ("black stool" in text or "tarry stool" in text, "Upper GI bleeding", "Urgent gastro assessment."),
        ("chest tightness" in text, "Acute coronary syndrome", "Urgent cardiac evaluation."),
    ]

    for condition, diagnosis, advice in high_triggers:
        if condition:
            return (
                f"RISK LEVEL: HIGH\n"
                f"POSSIBLE CONDITIONS: {diagnosis}\n"
                f"ADVICE: {advice}"
            )

    return (
        "RISK LEVEL: LOW\n"
        "POSSIBLE CONDITIONS: Non-specific symptoms, Mild viral illness\n"
        "ADVICE: Routine outpatient consultation recommended."
    )


if __name__ == "__main__":
    import sys as _sys
    print(f"[server] clinical-server ready in {_t.perf_counter() - _T0:.2f}s", file=_sys.stderr, flush=True)
    mcp.run(transport="stdio")