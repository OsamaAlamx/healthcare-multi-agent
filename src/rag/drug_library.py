"""
Curated over-the-counter medication knowledge base for common,
self-treatable conditions. This is the source data for the drug_library
vector index; agents surface these entries through the search_drug_library
MCP tool and may only recommend drugs listed here.
"""

DRUG_LIBRARY = [
    {
        "condition": "Tension headache",
        "symptoms": "mild to moderate headache, dull pressure around the forehead, stress-related head pain",
        "drug_name": "Paracetamol (Acetaminophen)",
        "drug_class": "Analgesic, antipyretic",
        "typical_dose": "500-1000 mg every 4-6 hours as needed (adults)",
        "limits": "maximum 3000 mg in 24 hours",
        "max_duration": "up to 3 days without medical advice",
        "precautions": "Avoid alcohol; check combination cold/flu products for hidden paracetamol; never double doses",
        "contraindications": "Severe liver disease, paracetamol hypersensitivity",
        "when_to_see_doctor": "Headache is sudden and severe, lasts beyond 3 days, follows a head injury, or comes with vision changes or fever",
    },
    {
        "condition": "Headache with inflammation, dental or muscular pain",
        "symptoms": "throbbing pain, pain with swelling, back pain, dental pain, pain after strain",
        "drug_name": "Ibuprofen",
        "drug_class": "NSAID",
        "typical_dose": "200-400 mg every 6-8 hours with food (adults)",
        "limits": "maximum 1200 mg per day without prescription",
        "max_duration": "up to 3 days",
        "precautions": "Always take with food; avoid alcohol; caution with asthma, kidney problems, or blood thinners; avoid in the third trimester of pregnancy",
        "contraindications": "Active stomach ulcer, NSAID allergy, severe kidney disease",
        "when_to_see_doctor": "Pain lasts beyond 3 days, stomach pain or black stools appear, or pain is severe and unexplained",
    },
    {
        "condition": "Fever",
        "symptoms": "raised temperature, chills, feeling hot, mild body aches with temperature",
        "drug_name": "Paracetamol (Acetaminophen)",
        "drug_class": "Antipyretic",
        "typical_dose": "500-1000 mg every 6 hours as needed (adults)",
        "limits": "maximum 3000 mg in 24 hours",
        "max_duration": "while fever persists, up to 3 days",
        "precautions": "Drink plenty of fluids; do not combine with other paracetamol-containing medicines",
        "contraindications": "Severe liver disease, paracetamol hypersensitivity",
        "when_to_see_doctor": "Fever above 39 C, lasting more than 3 days, or with stiff neck, rash, confusion, or breathlessness",
    },
    {
        "condition": "Common cold symptoms",
        "symptoms": "sneezing, runny nose, watery eyes, mild cold, itchy nose",
        "drug_name": "Cetirizine",
        "drug_class": "Antihistamine",
        "typical_dose": "10 mg once daily (adults)",
        "limits": "maximum 10 mg in 24 hours",
        "max_duration": "up to 7 days",
        "precautions": "May cause mild drowsiness; avoid alcohol; use caution when driving",
        "contraindications": "Severe kidney impairment",
        "when_to_see_doctor": "Fever with thick discoloured mucus, symptoms beyond 10 days, chest pain or shortness of breath",
    },
    {
        "condition": "Allergic rhinitis and hay fever",
        "symptoms": "seasonal allergies, pollen allergy, sneezing fits, itchy watery eyes, blocked nose from allergy",
        "drug_name": "Loratadine",
        "drug_class": "Non-sedating antihistamine",
        "typical_dose": "10 mg once daily (adults)",
        "limits": "maximum 10 mg in 24 hours",
        "max_duration": "as needed through the allergy season",
        "precautions": "Rarely causes drowsiness; if it does, avoid driving",
        "contraindications": "Known loratadine hypersensitivity",
        "when_to_see_doctor": "No relief within 1-2 weeks, wheezing develops, or suspected sinus infection with facial pain",
    },
]