import streamlit as st
from datetime import time
from database import get_db
from models import Appointment, DoctorUser, MedicalRecord, Patient, MedicalDocument
from memory.episodic_memory import retrieve_episodic_memories
from utils import DAYS_OF_WEEK, format_availability
from doctor_summary_service import generate_patient_clinical_summary, get_latest_clinical_summary


def show_doctor_dashboard():
    doctor_id = st.session_state.doctor_id
    doctor_name = st.session_state.doctor_name
    doctor_email = st.session_state.doctor_email
    doctor_spec = st.session_state.doctor_specialization

    with st.sidebar:
        st.markdown(f"### 🩺 {doctor_name}")
        st.markdown(f"**ID:** `{doctor_id}`")
        st.markdown(f"**Specialization:** {doctor_spec}")
        st.markdown(f"**Email:** {doctor_email}")
        st.markdown("---")

        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.query_params.clear()
            st.rerun()

    st.title(f"Doctor Panel — {doctor_name}")

    tab_appointments, tab_summaries, tab_patients, tab_profile = st.tabs([
        "📅 My Appointments",
        "🧾 Patient Summaries",
        "👥 Patient Lookup",
        "👤 Profile"
    ])

    with tab_appointments:
        _show_doctor_appointments(doctor_name)

    with tab_summaries:
        _show_patient_summaries(doctor_id, doctor_name)

    with tab_patients:
        _show_patient_lookup()

    with tab_profile:
        _show_doctor_profile(doctor_id)


def _show_doctor_appointments(doctor_name: str):
    st.subheader("📅 Consultation Schedule")
    with get_db() as db:
        appointments = db.query(Appointment).filter(
            Appointment.doctor_name.ilike(f"%{doctor_name}%")
        ).order_by(Appointment.created_at.desc()).all()

        if not appointments:
            st.info("No appointments recorded.")
            return

        for appt in appointments:
            with st.container():
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.markdown(f"**Patient:** {appt.patient_name}")
                with col2:
                    st.markdown(f"**Email:** {appt.patient_email}")
                with col3:
                    st.markdown(f"**Time:** {appt.appointment_time}")
                with col4:
                    st.markdown(f"**Status:** `{appt.status}`")
                st.markdown("---")


def _show_patient_summaries(doctor_id: str, doctor_name: str):
    st.subheader("🧾 Summarized Medical History — Booked Patients")
    st.caption(
        "Generate an AI-powered clinical summary (medical records + uploaded "
        "documents) for any patient who has booked an appointment with you."
    )

    # Extract everything to plain dicts INSIDE the session — after the with
    # block exits, the session commits/closes and ORM instances are detached.
    with get_db() as db:
        appointments = (
            db.query(Appointment)
            .filter(Appointment.doctor_name.ilike(f"%{doctor_name}%"))
            .order_by(Appointment.created_at.desc())
            .all()
        )

        # Deduplicate (keep most recent appointment per patient) AND
        # convert to plain dicts while the session is still open.
        seen = {}
        for appt in appointments:
            if appt.patient_id not in seen:
                seen[appt.patient_id] = {
                    "patient_id": appt.patient_id,
                    "patient_name": appt.patient_name,
                    "patient_email": appt.patient_email,
                    "appointment_time": appt.appointment_time,
                }

    unique_patients = list(seen.values())

    if not unique_patients:
        st.info("No booked patients yet.")
        return

    for p in unique_patients:
        patient_id = p["patient_id"]
        patient_name = p["patient_name"]
        patient_email = p["patient_email"]

        with st.container():
            st.markdown(f"### 👤 {patient_name}  `({patient_id})`")
            st.caption(f"📧 {patient_email} | Last appointment: {p['appointment_time']}")

            cached = get_latest_clinical_summary(patient_id)

            col1, col2 = st.columns([1, 2])
            with col1:
                label = "🔄 Regenerate Summary" if cached else "🧾 Generate Clinical Summary"
                if st.button(label, key=f"gen_summary_{patient_id}", use_container_width=True):
                    with st.spinner(f"Analyzing {patient_name}'s medical history..."):
                        try:
                            summary = generate_patient_clinical_summary(
                                patient_id=patient_id,
                                patient_name=patient_name,
                                patient_email=patient_email,
                                doctor_id=doctor_id
                            )
                            st.session_state[f"summary_{patient_id}"] = summary
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to generate summary: {str(e)}")

            with col2:
                if cached:
                    st.caption(
                        f"🕒 Last generated: "
                        f"{cached['generated_at'].strftime('%Y-%m-%d %H:%M')}"
                    )

            display_summary = st.session_state.get(f"summary_{patient_id}") or (
                cached["summary_text"] if cached else None
            )

            if display_summary:
                with st.expander("📄 View Clinical Summary", expanded=True):
                    st.markdown(display_summary)
            else:
                st.info("No summary generated yet. Click the button above.")

            _show_patient_documents_preview(patient_id)
            st.markdown("---")

def _show_patient_documents_preview(patient_id: str):
    with get_db() as db:
        docs = db.query(MedicalDocument).filter(
            MedicalDocument.patient_id == patient_id
        ).order_by(MedicalDocument.upload_date.desc()).all()

        if not docs:
            return

        with st.expander(f"📁 Uploaded Documents ({len(docs)})"):
            for doc in docs:
                status = "✅ Summarized" if doc.summary else "❌ Not summarized"
                st.markdown(
                    f"- **{doc.filename}** ({doc.document_type}) — "
                    f"{doc.upload_date.strftime('%Y-%m-%d')} — {status}"
                )


def _show_patient_lookup():
    st.subheader("👥 Patient Record Lookup")

    search = st.text_input("Enter Patient ID (e.g., PT_1) or Email")

    if not search:
        st.info("Enter a Patient ID or email to search records.")
        return

    with get_db() as db:
        patient = db.query(Patient).filter(
            (Patient.patient_id.ilike(f"%{search}%")) |
            (Patient.email.ilike(f"%{search}%"))
        ).first()

        if not patient:
            st.warning("No patient found.")
            return

        st.markdown(f"### Patient: {patient.name}")
        st.markdown(f"**ID:** `{patient.patient_id}` | **Email:** {patient.email}")

        records = db.query(MedicalRecord).filter(
            MedicalRecord.patient_email == patient.email,
            MedicalRecord.is_active == True
        ).all()

        if records:
            st.markdown("#### 🩺 Medical Records")
            for rec in records:
                st.markdown(f"- **{rec.record_type.upper()}**: {rec.details}")
        else:
            st.info("No medical records.")

        episodic = retrieve_episodic_memories(patient.patient_id)
        if episodic:
            st.markdown("#### 🧠 Episodic Memory (Allergies, etc.)")
            for mem in episodic:
                st.markdown(f"- **{mem['type'].upper()}**: {mem['content']}")


def _show_doctor_profile(doctor_id: str):
    st.subheader("👤 Profile Settings")

    with get_db() as db:
        doctor = db.query(DoctorUser).filter(DoctorUser.doctor_id == doctor_id).first()
        if not doctor:
            st.error("Doctor profile not found.")
            return

        st.markdown(f"**Name:** {doctor.name}")
        st.markdown(f"**Doctor ID:** `{doctor.doctor_id}`")
        st.markdown(f"**Specialization:** {doctor.specialization}")
        st.markdown(f"**Current Availability:** `{doctor.available_time}`")

        st.markdown("---")
        st.subheader("🗓️ Update Availability")

        with st.form("update_availability"):
            selected_days = st.multiselect(
                "Available Days",
                options=DAYS_OF_WEEK,
                default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            )

            col1, col2 = st.columns(2)
            with col1:
                start_time = st.time_input("From", value=time(9, 0), step=1800)
            with col2:
                end_time = st.time_input("To", value=time(17, 0), step=1800)

            submitted = st.form_submit_button("Update Availability", use_container_width=True)

        if submitted:
            if not selected_days:
                st.error("Please select at least one day.")
            elif start_time >= end_time:
                st.error("End time must be after start time.")
            else:
                new_availability = format_availability(selected_days, start_time, end_time)
                doctor.available_time = new_availability
                st.success(f"✅ Availability updated to: **{new_availability}**")
                st.rerun()