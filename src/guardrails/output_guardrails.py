"""
Output guardrails: every agent response passes through
apply_output_guardrails() before it is stored or displayed.

- Personal data belonging to other patients is masked.
- Prescriber responses are screened for restricted substances and must
  carry a medical disclaimer.
- Emergency-flagged conversations must contain urgent-care guidance.
"""
import re

from guardrails.audit import log_guardrail_event

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

CREDIT_CARD = r"\b(?:\d[ -]?){13,19}\b"
SSN = r"\b\d{3}-\d{2}-\d{4}\b"
PHONE = r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"

RESTRICTED_SUBSTANCES = [
    "oxycodone", "hydrocodone", "morphine", "fentanyl", "codeine", "tramadol",
    "methadone", "percocet", "vicodin", "oxycontin", "heroin", "opium",
    "alprazolam", "diazepam", "lorazepam", "clonazepam", "xanax", "valium",
    "ativan", "klonopin", "zolpidem", "amoxicillin", "azithromycin",
    "ciprofloxacin", "doxycycline", "amphetamines", "adderall", "ritalin",
    "methylphenidate", "ketamine", "barbiturates",
]

RECOMMENDATION_HINTS = re.compile(
    r"\b(?:take|use|try|recommend|suggest|dos(?:e|age)|tablet|capsule|mg|ml|daily|twice|every\s+\d+)\b",
    re.IGNORECASE,
)
MENTION_HINTS = re.compile(
    r"\b(?:allerg\w*|avoid|do\s+not|don't|dont|never|contraindicat\w*|intoleran\w*|history|recorded|instead)\b",
    re.IGNORECASE,
)

PRESCRIBER_DISCLAIMER = (
    "\n\n⚠️ This is general over-the-counter guidance, not a prescription. "
    "If symptoms persist beyond the recommended duration, worsen, or new "
    "symptoms appear, consult a doctor promptly."
)

PRESCRIBER_BLOCKED_RESPONSE = (
    "For safety reasons I can't suggest medication for this request. Please "
    "consult a doctor before taking any medicine. If your symptoms are "
    "severe or worsening, seek urgent medical care."
)

EMERGENCY_APPENDIX = (
    "\n\n⚠️ Your message mentioned symptoms that can be serious. If they are "
    "severe or getting worse, seek emergency medical care immediately."
)

EMERGENCY_ADVICE_PATTERN = re.compile(
    r"\b(?:emergency|immediately|urgent|right away|ambulance|emergency services)\b",
    re.IGNORECASE,
)

DISCLAIMER_PATTERN = re.compile(
    r"\b(?:consult\s+a\s+doctor|see\s+a\s+doctor|persist|worsen)\b",
    re.IGNORECASE,
)


def _mask_emails(response: str, patient_email: str) -> str:
    def replace(match):
        found = match.group(0)
        if patient_email and found.lower() == patient_email.lower():
            return found
        return "***@***.***"
    return EMAIL_PATTERN.sub(replace, response)


def _mask_sensitive(response: str) -> str:
    response = re.sub(CREDIT_CARD, "[REDACTED]", response)
    response = re.sub(SSN, "[REDACTED]", response)
    response = re.sub(PHONE, "[REDACTED]", response)
    return response


def _restricted_substance_recommendation(response: str):
    sentences = re.split(r"(?<=[.!?])\s+", response)
    for sentence in sentences:
        for substance in RESTRICTED_SUBSTANCES:
            if re.search(rf"\b{substance}\b", sentence, re.IGNORECASE):
                if RECOMMENDATION_HINTS.search(sentence) and not MENTION_HINTS.search(sentence):
                    return substance, sentence
    return None, None


def apply_output_guardrails(response: str, agent_name: str, patient_email: str = None,
                            emergency_input: bool = False, patient_id: str = None) -> dict:
    text = response or ""
    violations = []

    def record(rule, severity, action, excerpt):
        violations.append({
            "rule": rule, "severity": severity, "action": action,
            "excerpt": (excerpt or "")[:200],
        })
        log_guardrail_event(patient_id, "output", rule, severity, action, excerpt)

    masked = _mask_emails(_mask_sensitive(text), patient_email)
    if masked != text:
        record("pii_leak", "high", "redacted", "personal data of another patient masked")
        text = masked

    if agent_name == "Prescriber":
        substance, sentence = _restricted_substance_recommendation(text)
        if substance:
            record("restricted_substance", "high", "blocked", sentence)
            return {
                "response": PRESCRIBER_BLOCKED_RESPONSE,
                "violations": violations,
            }
        if not DISCLAIMER_PATTERN.search(text):
            text = text.rstrip() + PRESCRIBER_DISCLAIMER

    if emergency_input and not EMERGENCY_ADVICE_PATTERN.search(text):
        text = text.rstrip() + EMERGENCY_APPENDIX
        record("emergency_guidance_missing", "high", "flagged", "emergency advice appended")

    return {"response": text, "violations": violations}