from langchain.tools import tool
from database import get_db
from models import MedicalRecord, Patient


@tool
def record_medical_record(patient_email: str, record_type: str, details: str) -> str:
    """
    Saves a persistent medical history entry.
    record_type must be: allergy, chronic_condition, or medication.
    """
    try:
        with get_db() as db:
            patient = db.query(Patient).filter(Patient.email == patient_email).first()
            if not patient:
                return f"ERROR: Patient with email {patient_email} not found."

            db.query(MedicalRecord).filter(
                MedicalRecord.patient_email == patient_email,
                MedicalRecord.record_type == record_type,
                MedicalRecord.details.ilike(f"%{details}%"),
                MedicalRecord.is_active == True
            ).update({"is_active": False}, synchronize_session=False)

            db.add(MedicalRecord(
                patient_id=patient.patient_id,
                patient_email=patient_email,
                record_type=record_type,
                details=details,
                is_active=True
            ))
        return f"SUCCESS: {record_type.capitalize()} '{details}' saved for {patient_email}."
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def fetch_medical_history(patient_email: str) -> str:
    """
    Fetches the patient's updated clinical details and medications.
    """
    with get_db() as db:
        records = db.query(MedicalRecord).filter(
            MedicalRecord.patient_email == patient_email,
            MedicalRecord.is_active == True
        ).all()

        if not records:
            return "No active medical history found."

        history = {}
        for r in records:
            history.setdefault(r.record_type, []).append(r.details)

        formatted = "\n".join([f"- {k.upper()}: {', '.join(v)}" for k, v in history.items()])
        return f"Medical Records for {patient_email}:\n{formatted}"