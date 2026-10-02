"""
MCP Server 2: Scheduling & Communication
Handles: doctor search, appointment booking, email notifications
"""
import sys
import time as _t
_T0 = _t.perf_counter()
import os
import re
import smtplib
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from database import get_db
from models import Appointment, Patient, DoctorUser

load_dotenv()

mcp = FastMCP("scheduling-server")

EMAIL = os.getenv("SENDER_EMAIL")
PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


@mcp.tool()
def fetch_doctor_schedule(query: str) -> str:
    """
    Finds doctor availability and specialities. Query can be specialization or name.
    """
    with get_db() as db:
        doctors = db.query(DoctorUser).filter(
            (DoctorUser.name.ilike(f"%{query}%")) |
            (DoctorUser.specialization.ilike(f"%{query}%"))
        ).all()

        if not doctors:
            return f"ERROR: No doctor or specialization matching '{query}' found."

        results = [
            f"Doctor ID: {doc.doctor_id}\n"
            f"Name: {doc.name}\n"
            f"Specialization: {doc.specialization}\n"
            f"Available: {doc.available_time}"
            for doc in doctors
        ]
        return "\n---\n".join(results)


@mcp.tool()
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


@mcp.tool()
def send_email(email: str, patient_name: str, doctor_name: str, appointment_time: str) -> str:
    """
    Sends an appointment confirmation email to the patient.
    """
    email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if not email or not re.match(email_regex, email):
        return "ERROR: Invalid email address."

    if not EMAIL or not PASSWORD:
        return "ERROR: Email credentials not configured."

    try:
        html = f"""
        <html><body>
            <h2>Appointment Confirmed</h2>
            <p><b>Patient:</b> {patient_name}</p>
            <p><b>Doctor:</b> {doctor_name}</p>
            <p><b>Time:</b> {appointment_time}</p>
        </body></html>
        """
        msg = MIMEText(html, "html")
        msg["Subject"] = "Medical Appointment Confirmation"
        msg["From"] = EMAIL
        msg["To"] = email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL, PASSWORD)
            server.sendmail(EMAIL, email, msg.as_string())

        return f"SUCCESS: Confirmation email sent to {email}."
    except Exception as e:
        return f"ERROR: Email failed. {str(e)}"


if __name__ == "__main__":
    import sys as _sys
    print(f"[server] clinical-server ready in {_t.perf_counter() - _T0:.2f}s", file=_sys.stderr, flush=True)
    mcp.run(transport="stdio")