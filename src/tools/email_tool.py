import os
import re
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv()

EMAIL = os.getenv("SENDER_EMAIL")
PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _template(name: str, doctor: str, time: str) -> str:
    return f"""
    <html><body>
        <h2>Appointment Confirmed</h2>
        <p><b>Patient:</b> {name}</p>
        <p><b>Doctor:</b> {doctor}</p>
        <p><b>Time:</b> {time}</p>
    </body></html>
    """


@tool
def send_email(email: str, patient_name: str, doctor_name: str, appointment_time: str) -> str:
    """
    Sends an appointment confirmation email to the patient.
    """
    if not email or not re.match(EMAIL_REGEX, email):
        return "ERROR: Invalid email address."

    if not EMAIL or not PASSWORD:
        return "ERROR: Email credentials not configured."

    try:
        msg = MIMEText(_template(patient_name, doctor_name, appointment_time), "html")
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