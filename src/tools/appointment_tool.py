from langchain.tools import tool
from database import get_db
from models import Appointment, Patient


@tool
def book_appointment(patient_name: str, doctor_name: str, appointment_time: str, patient_email: str) -> str:
    """
    Schedules a clinical appointment for a patient.
    Requires patient_name, doctor_name, appointment_time, and patient_email.
    """
    try:
        with get_db() as db:
            patient = db.query(Patient).filter(Patient.email == patient_email).first()
            if not patient:
                return f"ERROR: Patient with email {patient_email} is not registered."

            db.add(Appointment(
                patient_id=patient.patient_id,
                patient_name=patient_name,
                patient_email=patient_email,
                doctor_name=doctor_name,
                appointment_time=appointment_time,
                status="Scheduled"
            ))
        return (
            f"SUCCESS: Appointment booked for {patient_name} "
            f"with {doctor_name} at {appointment_time}."
        )
    except Exception as e:
        return f"ERROR: Failed to book appointment. {str(e)}"