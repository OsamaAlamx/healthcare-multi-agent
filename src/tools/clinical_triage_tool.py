from langchain.tools import tool


@tool
def clinical_triage(symptoms: str) -> str:
    """
    Maps symptoms to diagnoses and clinical risk level.
    """
    text = symptoms.lower()

    critical_triggers = [
        ("chest pain" in text and "left" in text,
         "Myocardial infarction (heart attack)",
         "Seek emergency medical help immediately."),
        ("shortness of breath" in text,
         "Pulmonary embolism, Asthma attack",
         "Immediate emergency evaluation required."),
        ("sudden weakness" in text or "one side weakness" in text,
         "Stroke (CVA), TIA",
         "Call emergency services immediately."),
        ("slurred speech" in text,
         "Stroke, Neurological emergency",
         "Immediate hospital evaluation required."),
        ("loss of consciousness" in text or "unconscious" in text,
         "Cardiac arrest, Seizure",
         "Emergency medical intervention required."),
        ("vomiting blood" in text,
         "Upper gastrointestinal bleed",
         "Emergency hospital admission required."),
        ("severe headache" in text and "sudden" in text,
         "Brain hemorrhage",
         "Immediate CT scan and emergency care required."),
        ("anaphylaxis" in text or "severe allergic reaction" in text,
         "Anaphylactic shock",
         "Administer emergency treatment immediately."),
        ("high fever" in text and "stiff neck" in text,
         "Meningitis",
         "Immediate hospital admission required."),
    ]

    for condition, diagnosis, advice in critical_triggers:
        if condition:
            return (
                f"RISK LEVEL: CRITICAL\n"
                f"POSSIBLE CONDITIONS: {diagnosis}\n"
                f"ADVICE: {advice}"
            )

    high_triggers = [
        ("seizure" in text,
         "Epilepsy, Brain injury",
         "Urgent neurological evaluation recommended."),
        ("severe abdominal pain" in text,
         "Appendicitis, Pancreatitis",
         "Urgent surgical evaluation recommended."),
        ("black stool" in text or "tarry stool" in text,
         "Upper gastrointestinal bleeding",
         "Urgent gastroenterology assessment required."),
        ("chest tightness" in text,
         "Acute coronary syndrome, Angina",
         "Urgent cardiac evaluation required."),
    ]

    for condition, diagnosis, advice in high_triggers:
        if condition:
            return (
                f"RISK LEVEL: HIGH\n"
                f"POSSIBLE CONDITIONS: {diagnosis}\n"
                f"ADVICE: {advice}"
            )

    return (
        "RISK LEVEL: LOW\n"
        "POSSIBLE CONDITIONS: Non-specific symptoms, Mild viral illness\n"
        "ADVICE: Routine outpatient consultation recommended."
    )