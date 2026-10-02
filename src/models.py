from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float
from datetime import datetime
from database import Base


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DoctorUser(Base):
    __tablename__ = "doctor_users"
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    specialization = Column(String, nullable=False)
    available_time = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    patient_name = Column(String)
    patient_email = Column(String)
    doctor_id = Column(String, index=True, nullable=True)
    doctor_name = Column(String)
    appointment_time = Column(String)
    status = Column(String, default="Scheduled")
    created_at = Column(DateTime, default=datetime.utcnow)


class MedicalRecord(Base):
    __tablename__ = "medical_records"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    patient_email = Column(String, index=True)
    record_type = Column(String, index=True)
    details = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EpisodicMemory(Base):
    __tablename__ = "episodic_memory"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    memory_type = Column(String, index=True)
    content = Column(Text)
    context = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    agent_name = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class MedicalDocument(Base):
    __tablename__ = "medical_documents"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)           # Cached summary
    document_type = Column(String, default="report") # report, prescription, discharge
    upload_date = Column(DateTime, default=datetime.utcnow)


class ClinicalSummary(Base):
    __tablename__ = "clinical_summaries"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    summary_text = Column(Text)
    generated_by = Column(String, nullable=True)   # doctor_id who triggered it
    generated_at = Column(DateTime, default=datetime.utcnow)


class GuardrailLog(Base):
    __tablename__ = "guardrail_logs"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True, nullable=True)
    guardrail_type = Column(String)   # "input" or "output"
    rule_name = Column(String)       # prompt_injection, pii_leak, ...
    severity = Column(String)        # low / medium / high
    action = Column(String)          # blocked / redacted / flagged
    excerpt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PrescriptionLog(Base):
    __tablename__ = "prescription_logs"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    patient_email = Column(String)
    condition = Column(String, nullable=True)
    drug_name = Column(String, nullable=True)
    dose = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id = Column(Integer, primary_key=True, index=True)
    suite = Column(String)             # triage / guardrails / rag / router / e2e
    total_cases = Column(Integer)
    passed = Column(Integer)
    failed = Column(Integer)
    pass_rate = Column(Float)
    duration_seconds = Column(Float, nullable=True)
    report_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)