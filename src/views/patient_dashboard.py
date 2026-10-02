import os
import streamlit as st
from pypdf import PdfReader
from agent_router import handle_patient_query
from memory.conversation_memory import load_conversation_display, clear_conversation
from memory.episodic_memory import retrieve_episodic_memories
from database import get_db
from models import Appointment, MedicalRecord, MedicalDocument
from rag.build_rag_indexes import ingest_document

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

TAB_LABELS = [
    "🏥 Receptionist",
    "🧠 Symptom Analysis",
    "🧬 Medical Memory",
    "💊 Prescriptions",
    "📋 My Records"
]


def show_patient_dashboard():
    patient_id = st.session_state.patient_id
    patient_name = st.session_state.patient_name
    patient_email = st.session_state.patient_email

    if "active_tab_label" not in st.session_state:
        st.session_state.active_tab_label = TAB_LABELS[0]

    with st.sidebar:
        st.markdown(f"### 👤 {patient_name}")
        st.markdown(f"**ID:** `{patient_id}`")
        st.markdown(f"**Email:** {patient_email}")
        st.markdown("---")

        if st.button("🗑️ Clear Chat History", use_container_width=True):
            clear_conversation(patient_id)
            st.session_state.active_tab_label = TAB_LABELS[0]
            st.rerun()

        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.query_params.clear()
            st.rerun()

    st.title(f"Welcome, {patient_name}!")

    selected_tab = st.radio(
        "Navigation",
        TAB_LABELS,
        index=TAB_LABELS.index(st.session_state.active_tab_label),
        horizontal=True,
        label_visibility="collapsed",
        key="nav_radio"
    )
    st.session_state.active_tab_label = selected_tab
    st.markdown("---")

    user_input = st.chat_input("Type your message here...")

    if user_input:
        result = None
        with st.spinner("Processing..."):
            try:
                result = handle_patient_query(
                    patient_id=patient_id,
                    patient_name=patient_name,
                    patient_email=patient_email,
                    user_message=user_input
                )
            except TimeoutError:
                st.error(
                    "⏱️ The assistant took too long to respond (over 120s). "
                    "Please try again — if this keeps happening, restart the app."
                )
            except Exception as e:
                st.error(f"Something went wrong: {e}")

        if result:
            tab_index = result.get("tab_index", 0)
            if 0 <= tab_index < len(TAB_LABELS):
                st.session_state.active_tab_label = TAB_LABELS[tab_index]
            st.rerun()

    conversation = load_conversation_display(patient_id)
    grouped = _group_conversation_by_agent(conversation)

    if selected_tab == TAB_LABELS[0]:
        st.subheader("🏥 Receptionist Agent")
        st.caption("Book appointments, find doctors, and manage scheduling.")
        _render_chat(grouped["receptionist"])

    elif selected_tab == TAB_LABELS[1]:
        st.subheader("🧠 Symptom Analysis Agent")
        st.caption("Describe symptoms for triage and risk assessment.")
        _render_chat(grouped["reasoning"])

    elif selected_tab == TAB_LABELS[2]:
        st.subheader("🧬 Medical Memory Agent")
        st.caption("Store and retrieve allergies, medications, and chronic conditions.")
        _render_chat(grouped["memory"])
        episodic = retrieve_episodic_memories(patient_id)
        if episodic:
            st.markdown("---")
            st.markdown("#### 🧠 Auto-Tracked Episodic Memory")
            for mem in episodic:
                st.markdown(f"- **{mem['type'].upper()}**: {mem['content']}")

    elif selected_tab == TAB_LABELS[3]:
        st.subheader("💊 Prescriptions Agent")
        st.caption("Over-the-counter guidance for common, minor conditions only.")
        _render_chat(grouped["prescriber"])

    elif selected_tab == TAB_LABELS[4]:
        st.subheader("📋 My Medical Records")
        _show_patient_records(patient_id, patient_email)
        st.markdown("---")
        _show_document_uploader(patient_id)


# PDF UPLOAD SECTION

def _show_document_uploader(patient_id: str):
    st.markdown("#### 📎 Upload Medical Document (PDF)")
    st.caption("Uploaded documents are summarized and reviewed by your doctor at your appointment.")

    doc_type = st.selectbox(
        "Document Type",
        ["Test Report", "Prescription", "Discharge Summary", "Lab Results", "Other"],
        key="doc_type_select"
    )

    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        key="pdf_uploader"
    )

    if uploaded_file is not None:
        st.info(f"📄 File: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

        if st.button("⬆️ Upload & Extract Text", use_container_width=True):
            with st.spinner("Extracting text from PDF..."):
                try:
                    patient_dir = os.path.join(UPLOAD_DIR, patient_id)
                    os.makedirs(patient_dir, exist_ok=True)
                    file_path = os.path.join(patient_dir, uploaded_file.name)

                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    reader = PdfReader(file_path)
                    pages_text = []
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text()
                        if text:
                            pages_text.append(f"--- Page {i+1} ---\n{text}")

                    extracted_text = "\n\n".join(pages_text)

                    if not extracted_text.strip():
                        st.warning("⚠️ No readable text found in this PDF. It may be a scanned image.")
                        extracted_text = "[No extractable text — scanned document]"

                    document_type = doc_type.lower().replace(" ", "_")

                    with get_db() as db:
                        doc = MedicalDocument(
                            patient_id=patient_id,
                            filename=uploaded_file.name,
                            file_path=file_path,
                            extracted_text=extracted_text,
                            document_type=document_type
                        )
                        db.add(doc)
                        db.flush()
                        doc_id = doc.id

                    ingest_document(
                        doc_id, patient_id, uploaded_file.name,
                        document_type, extracted_text
                    )

                    st.success(f"✅ Uploaded successfully! Extracted {len(extracted_text)} characters.")
                    st.rerun()

                except Exception as e:
                    st.error(f"Upload failed: {str(e)}")

    _show_uploaded_documents(patient_id)


def _show_uploaded_documents(patient_id: str):
    with get_db() as db:
        docs = db.query(MedicalDocument).filter(
            MedicalDocument.patient_id == patient_id
        ).order_by(MedicalDocument.upload_date.desc()).all()

        if not docs:
            st.info("No documents uploaded yet.")
            return

        st.markdown("#### 📁 Your Uploaded Documents")
        for doc in docs:
            with st.expander(f"📄 {doc.filename} ({doc.document_type})"):
                extracted = doc.extracted_text or ""
                searchable = bool(extracted) and not extracted.startswith("[No extractable text")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Uploaded:** {doc.upload_date.strftime('%Y-%m-%d %H:%M')}")
                with col2:
                    st.markdown(f"**Indexed for search:** {'✅ Yes' if searchable else '❌ No'}")
                st.markdown("**Text Preview:**")
                preview = extracted[:300]
                st.code(preview + "..." if len(extracted) > 300 else preview, language="text")


# CHAT HELPERS

def _group_conversation_by_agent(conversation: list) -> dict:
    grouped = {"receptionist": [], "reasoning": [], "memory": [], "prescriber": []}

    i = 0
    while i < len(conversation):
        msg = conversation[i]
        if msg["role"] == "user":
            agent_key = None
            if i + 1 < len(conversation) and conversation[i + 1]["role"] == "assistant":
                agent_key = _agent_name_to_key(conversation[i + 1].get("agent_name", ""))
            if agent_key and agent_key in grouped:
                grouped[agent_key].append(msg)
                grouped[agent_key].append(conversation[i + 1])
                i += 2
                continue
            elif agent_key:
                i += 2
                continue
            else:
                grouped["receptionist"].append(msg)
                i += 1
        else:
            agent_key = _agent_name_to_key(msg.get("agent_name", ""))
            if agent_key and agent_key in grouped:
                grouped[agent_key].append(msg)
            i += 1
    return grouped


def _agent_name_to_key(agent_name: str) -> str:
    if not agent_name:
        return None
    if "Receptionist" in agent_name:
        return "receptionist"
    if "Reasoning" in agent_name:
        return "reasoning"
    if "Memory" in agent_name:
        return "memory"
    if "Prescriber" in agent_name:
        return "prescriber"
    if "Summarizer" in agent_name:
        return "summarizer"
    if "System" in agent_name:
        return "receptionist"
    return None


def _render_chat(messages: list):
    if not messages:
        st.info("💬 No messages yet. Start a conversation using the chat box below!")
        return
    for msg in messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant" and msg.get("agent_name"):
                st.caption(msg["agent_name"])
            st.markdown(msg["content"])


def _show_patient_records(patient_id: str, patient_email: str):
    with get_db() as db:
        appointments = db.query(Appointment).filter(
            Appointment.patient_id == patient_id
        ).order_by(Appointment.created_at.desc()).all()

        if appointments:
            st.markdown("#### 📅 Scheduled Appointments")
            for appt in appointments:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**Doctor:** {appt.doctor_name}")
                with col2:
                    st.markdown(f"**Time:** {appt.appointment_time}")
                with col3:
                    st.markdown(f"**Status:** `{appt.status}`")
                st.markdown("---")
        else:
            st.info("No scheduled appointments.")

        records = db.query(MedicalRecord).filter(
            MedicalRecord.patient_email == patient_email,
            MedicalRecord.is_active == True
        ).all()

        if records:
            st.markdown("#### 🩺 Medical Records")
            for rec in records:
                st.markdown(f"- **{rec.record_type.upper()}**: {rec.details}")
        else:
            st.info("No medical records on file.")

        episodic = retrieve_episodic_memories(patient_id)
        if episodic:
            st.markdown("#### 🧠 Episodic Memory")
            for mem in episodic:
                st.markdown(f"- **{mem['type'].upper()}**: {mem['content']}")