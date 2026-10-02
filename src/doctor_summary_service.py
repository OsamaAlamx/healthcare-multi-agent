"""
Doctor-facing clinical summary generation.

Aggregates a patient's medical records + uploaded documents into a single
clinician-oriented summary, using the MCP-powered doctor_summary agent,
and caches the result so it doesn't need regeneration on every view.
"""
from langchain_core.messages import HumanMessage

from agents.agent_factory import make_doctor_summary_factory
from mcp_client import run_agent_with_mcp
from guardrails.output_guardrails import apply_output_guardrails
from database import get_db
from models import ClinicalSummary


def generate_patient_clinical_summary(
    patient_id: str,
    patient_name: str,
    patient_email: str,
    doctor_id: str = None
) -> str:
    """
    Runs the Doctor Summary Agent to produce a full clinical summary of the
    patient's medical history + uploaded documents, then caches it.
    """
    factory = make_doctor_summary_factory(patient_id, patient_name, patient_email)

    messages = [
        HumanMessage(
            content=(
                f"Generate a complete clinical summary for patient {patient_name} "
                f"for the treating doctor's review. Include allergies, chronic "
                f"conditions, medications, and findings from ALL uploaded documents."
            )
        )
    ]

    result = run_agent_with_mcp("doctor_summary", factory, messages)
    summary_text = result["messages"][-1].content or "No summary could be generated."

    guard = apply_output_guardrails(
        summary_text, "Doctor Summary", patient_email=patient_email
    )
    summary_text = guard["response"]

    with get_db() as db:
        db.add(ClinicalSummary(
            patient_id=patient_id,
            summary_text=summary_text,
            generated_by=doctor_id
        ))

    return summary_text


def get_latest_clinical_summary(patient_id: str) -> dict:
    """Returns the most recently cached summary for a patient, if any."""
    with get_db() as db:
        record = (
            db.query(ClinicalSummary)
            .filter(ClinicalSummary.patient_id == patient_id)
            .order_by(ClinicalSummary.generated_at.desc())
            .first()
        )
        if not record:
            return None
        return {
            "summary_text": record.summary_text,
            "generated_at": record.generated_at,
            "generated_by": record.generated_by
        }