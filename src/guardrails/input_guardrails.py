"""
Input guardrails: every patient message passes through
apply_input_guardrails() before it reaches an agent.

Checks, in order of severity:
1. Prompt injection attempts   -> blocked
2. Abusive language            -> blocked
3. Out-of-scope requests       -> blocked
4. Sensitive personal data     -> redacted before storage or LLM exposure
5. Emergency red-flag symptoms -> flagged, which forces routing to the
                                  Reasoning Agent and strengthens the
                                  output safety check
"""
import re

from guardrails.audit import log_guardrail_event

INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+|any\s+|your\s+|the\s+)?(?:previous|prior|above|earlier|past)\s+(?:instructions|prompts|rules|messages|context)",
    r"disregard\s+(?:your\s+|all\s+|the\s+)?(?:instructions|rules|prompts|guidelines)",
    r"forget\s+(?:your\s+|all\s+|the\s+)?(?:instructions|rules|prompts|training|everything)",
    r"(?:reveal|show|print|repeat|display|give)\s+(?:me\s+)?(?:your\s+)?(?:system\s+prompt|initial\s+instructions|hidden\s+instructions|developer\s+instructions)",
    r"you\s+are\s+now\s+(?!a\s+(?:medical|health|doctor))",
    r"act\s+as\s+(?:if\s+you\s+are\s+)?(?:a|an)\s+(?!doctor|medical|physician|nurse)",
    r"(?:developer|jailbreak|DAN|god)\s+mode",
    r"repeat\s+everything\s+(?:above|before|i\s+said)",
]

ABUSE_PATTERNS = [
    r"\b(?:stupid|idiot|dumb|moron|retard|shut\s+up)\b",
]

OFF_SCOPE_PATTERNS = [
    r"\b(?:write|compose|draft)\b.*\b(?:essay|poem|story|song|article|blog|speech)\b",
    r"\b(?:write|fix|debug|refactor|build)\b.*\b(?:code|program|script|function|app|website)\b",
    r"\b(?:stock|share|crypto|bitcoin|forex|trading)\b.*\b(?:tip|advice|predict|price|recommend)\b",
    r"\b(?:do|solve|complete|finish)\b.*\b(?:homework|assignment|project)\b",
    r"\b(?:tell|say)\b.*\b(?:joke|funny\s+story)\b",
]

SENSITIVE_DATA_PATTERNS = {
    "credit_card": r"\b(?:\d[ -]?){13,19}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "phone": r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)",
}

REDACTED = "[REDACTED]"

EMERGENCY_KEYWORDS = [
    "chest pain", "chest tightness", "shortness of breath", "can't breathe",
    "cant breathe", "cannot breathe", "not breathing", "trouble breathing",
    "difficulty breathing",
    "slurred speech", "face drooping", "weakness on one side",
    "numbness on one side", "one side weakness",
    "loss of consciousness", "unconscious", "passed out", "fainted",
    "vomiting blood", "coughing blood", "blood in vomit",
    "seizure", "convulsion",
    "anaphylaxis", "severe allergic reaction", "throat closing", "throat is closing",
    "worst headache of my life", "sudden severe headache",
    "suicid", "kill myself", "self harm", "end my life",
]

BLOCKED_RESPONSES = {
    "prompt_injection": (
        "I'm unable to process that request. I can only help with medical "
        "questions, appointment booking, and your saved medical records."
    ),
    "abusive_language": (
        "Please keep the conversation respectful so I can continue helping you."
    ),
    "off_topic_request": (
        "This assistant handles medical and scheduling topics only. Please ask "
        "a health-related question or request an appointment."
    ),
}


def _match_any(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def apply_input_guardrails(message: str, patient_id: str = None) -> dict:
    text = message or ""
    violations = []

    def record(rule, severity, action, excerpt):
        violations.append({
            "rule": rule, "severity": severity, "action": action,
            "excerpt": (excerpt or "")[:200],
        })
        log_guardrail_event(patient_id, "input", rule, severity, action, excerpt)

    blocked_rule = None
    for rule, patterns in (
        ("prompt_injection", INJECTION_PATTERNS),
        ("abusive_language", ABUSE_PATTERNS),
        ("off_topic_request", OFF_SCOPE_PATTERNS),
    ):
        matched = _match_any(patterns, text)
        if matched:
            record(rule, "high", "blocked", matched)
            blocked_rule = rule
            break

    if blocked_rule:
        return {
            "allowed": False,
            "message": BLOCKED_RESPONSES[blocked_rule],
            "flags": {"emergency": False},
            "violations": violations,
        }

    sanitized = text
    for rule, pattern in SENSITIVE_DATA_PATTERNS.items():
        if re.search(pattern, sanitized):
            sanitized = re.sub(pattern, REDACTED, sanitized)
            record(rule, "medium", "redacted", "sensitive data removed")

    lowered = sanitized.lower()
    emergency = any(keyword in lowered for keyword in EMERGENCY_KEYWORDS)
    if emergency:
        record("emergency_symptoms", "high", "flagged", "emergency keywords detected")

    return {
        "allowed": True,
        "message": sanitized,
        "flags": {"emergency": emergency},
        "violations": violations,
    }