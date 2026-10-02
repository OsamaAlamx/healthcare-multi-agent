import os
import sys
from dotenv import load_dotenv

load_dotenv()

import streamlit as st
from database import init_db

# Initialize database on startup
init_db()

# Create uploads directory if it doesn't exist
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Page config MUST be first Streamlit call
st.set_page_config(
    page_title="Multi-Agent Medical AI System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def _build_rag_indexes():
    """Builds the drug library and medical records vector indexes once per
    process. Raises on failure so the real error is visible in the console."""
    from rag.build_rag_indexes import ensure_indexes
    ensure_indexes()
    return True


def _start_mcp_warmup():
    """
    Non-blocking MCP warm-up: spawns servers in a background daemon thread
    so the UI is interactive immediately. The mcp_client module-level flag
    makes this a no-op on every rerun after the first.
    """
    from mcp_client import start_background_warmup
    start_background_warmup(["receptionist", "reasoning", "memory", "prescriber"])


try:
    _build_rag_indexes()
except Exception as e:
    st.warning(
        "The RAG indexes could not be built — drug recommendations and "
        "semantic record search may be unavailable for this session."
    )
    print(f"[rag] ensure_indexes FAILED: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

_start_mcp_warmup()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Session restoration from URL
if not st.session_state.logged_in:
    saved_role = st.query_params.get("role")
    saved_uid = st.query_params.get("uid")

    if saved_role and saved_uid:
        from database import get_db
        from models import Patient, DoctorUser
        with get_db() as db:
            if saved_role == "patient":
                patient = db.query(Patient).filter(Patient.patient_id == saved_uid).first()
                if patient:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "patient"
                    st.session_state.patient_id = patient.patient_id
                    st.session_state.patient_name = patient.name
                    st.session_state.patient_email = patient.email
            elif saved_role == "doctor":
                doctor = db.query(DoctorUser).filter(DoctorUser.doctor_id == saved_uid).first()
                if doctor:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "doctor"
                    st.session_state.doctor_id = doctor.doctor_id
                    st.session_state.doctor_name = doctor.name
                    st.session_state.doctor_email = doctor.email
                    st.session_state.doctor_specialization = doctor.specialization

# Routing
if not st.session_state.logged_in:
    from views.auth_page import show_auth_page
    show_auth_page()
elif st.session_state.get("user_role") == "patient":
    from views.patient_dashboard import show_patient_dashboard
    show_patient_dashboard()
elif st.session_state.get("user_role") == "doctor":
    from views.doctor_dashboard import show_doctor_dashboard
    show_doctor_dashboard()
else:
    st.error("Invalid session state.")
    if st.button("Reset"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.query_params.clear()
        st.rerun()