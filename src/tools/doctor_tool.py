from langchain.tools import tool
from database import get_db
from models import DoctorUser


@tool
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