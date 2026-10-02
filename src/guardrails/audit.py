"""
Persists guardrail decisions so every blocked, redacted, or flagged message
is auditable. Logging failures are swallowed on purpose: safety checks must
never break the conversation flow.
"""
from database import get_db
from models import GuardrailLog


def log_guardrail_event(patient_id: str, guardrail_type: str, rule_name: str,
                        severity: str, action: str, excerpt: str = None):
    try:
        with get_db() as db:
            db.add(GuardrailLog(
                patient_id=patient_id,
                guardrail_type=guardrail_type,
                rule_name=rule_name,
                severity=severity,
                action=action,
                excerpt=(excerpt or "")[:500]
            ))
    except Exception:
        pass