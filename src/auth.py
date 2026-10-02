import bcrypt
from database import get_db
from models import Patient, DoctorUser


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def generate_patient_id() -> str:
    with get_db() as db:
        count = db.query(Patient).count()
        return f"PT_{count + 1}"


def generate_doctor_id() -> str:
    with get_db() as db:
        count = db.query(DoctorUser).count()
        return f"DOC_{count + 1}"


def register_patient(name: str, email: str, password: str) -> dict:
    try:
        with get_db() as db:
            existing = db.query(Patient).filter(Patient.email == email).first()
            if existing:
                return {"success": False, "error": "Email already registered."}

            patient_id = f"PT_{db.query(Patient).count() + 1}"
            db.add(Patient(
                patient_id=patient_id,
                name=name,
                email=email,
                password_hash=hash_password(password)
            ))
        return {"success": True, "patient_id": patient_id, "name": name, "email": email}
    except Exception as e:
        return {"success": False, "error": str(e)}


def login_patient(email: str, password: str) -> dict:
    with get_db() as db:
        patient = db.query(Patient).filter(Patient.email == email).first()
        if not patient:
            return {"success": False, "error": "Email not found."}
        if not verify_password(password, patient.password_hash):
            return {"success": False, "error": "Incorrect password."}
        return {
            "success": True,
            "patient_id": patient.patient_id,
            "name": patient.name,
            "email": patient.email
        }


def register_doctor(name: str, email: str, password: str, specialization: str, available_time: str) -> dict:
    try:
        with get_db() as db:
            existing = db.query(DoctorUser).filter(DoctorUser.email == email).first()
            if existing:
                return {"success": False, "error": "Email already registered."}

            doctor_id = f"DOC_{db.query(DoctorUser).count() + 1}"
            db.add(DoctorUser(
                doctor_id=doctor_id,
                name=name,
                email=email,
                password_hash=hash_password(password),
                specialization=specialization,
                available_time=available_time
            ))
        return {"success": True, "doctor_id": doctor_id, "name": name, "email": email}
    except Exception as e:
        return {"success": False, "error": str(e)}


def login_doctor(email: str, password: str) -> dict:
    with get_db() as db:
        doctor = db.query(DoctorUser).filter(DoctorUser.email == email).first()
        if not doctor:
            return {"success": False, "error": "Email not found."}
        if not verify_password(password, doctor.password_hash):
            return {"success": False, "error": "Incorrect password."}
        return {
            "success": True,
            "doctor_id": doctor.doctor_id,
            "name": doctor.name,
            "email": doctor.email,
            "specialization": doctor.specialization
        }