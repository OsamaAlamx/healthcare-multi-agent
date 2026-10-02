import streamlit as st
from datetime import time
from auth import register_patient, login_patient, register_doctor, login_doctor
from utils import DAYS_OF_WEEK, format_availability


def show_auth_page():
    st.title("🏥 Medical AI System")
    st.markdown("---")

    role = st.radio("I am a:", ["Patient", "Doctor"], horizontal=True)
    action = st.radio("Action:", ["Sign In", "Sign Up"], horizontal=True)

    st.markdown("---")

    if role == "Patient":
        if action == "Sign Up":
            _patient_signup()
        else:
            _patient_signin()
    else:
        if action == "Sign Up":
            _doctor_signup()
        else:
            _doctor_signin()


def _patient_signup():
    st.subheader("📋 Patient Registration")

    with st.form("patient_signup_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Register", use_container_width=True)

    if submitted:
        if not name or not email or not password:
            st.error("All fields are required.")
            return
        if password != confirm_password:
            st.error("Passwords do not match.")
            return
        if len(password) < 6:
            st.error("Password must be at least 6 characters.")
            return

        result = register_patient(name, email, password)
        if result["success"]:
            st.success(f"✅ Registered! Your Patient ID: **{result['patient_id']}**")
            st.info("Please sign in to continue.")
        else:
            st.error(f"Registration failed: {result['error']}")


def _patient_signin():
    st.subheader("🔐 Patient Sign In")

    with st.form("patient_signin_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please enter email and password.")
            return

        result = login_patient(email, password)
        if result["success"]:
            st.session_state.logged_in = True
            st.session_state.user_role = "patient"
            st.session_state.patient_id = result["patient_id"]
            st.session_state.patient_name = result["name"]
            st.session_state.patient_email = result["email"]
            
            # ✅ Save to URL so it persists on Page Refresh
            st.query_params["role"] = "patient"
            st.query_params["uid"] = result["patient_id"]
            st.rerun()
        else:
            st.error(f"Login failed: {result['error']}")


def _doctor_signup():
    st.subheader("📋 Doctor Registration")

    with st.form("doctor_signup_form"):
        name = st.text_input("Full Name (e.g., Dr. Smith)")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        specialization = st.selectbox("Specialization", [
            "General Physician", "Cardiologist", "Neurologist",
            "Dermatologist", "Pediatrician", "Orthopedic",
            "Psychiatrist", "ENT Specialist", "Ophthalmologist"
        ])

        st.markdown("##### 🗓️ Availability")

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

        submitted = st.form_submit_button("Register", use_container_width=True)

    if submitted:
        if not name or not email or not password:
            st.error("Name, email, and password are required.")
            return
        if password != confirm_password:
            st.error("Passwords do not match.")
            return
        if len(password) < 6:
            st.error("Password must be at least 6 characters.")
            return
        if not selected_days:
            st.error("Please select at least one available day.")
            return
        if start_time >= end_time:
            st.error("End time must be after start time.")
            return

        available_time = format_availability(selected_days, start_time, end_time)

        result = register_doctor(name, email, password, specialization, available_time)
        if result["success"]:
            st.success(f"✅ Registered! Your Doctor ID: **{result['doctor_id']}**")
            st.info(f"Availability set: **{available_time}**")
            st.info("Please sign in to continue.")
        else:
            st.error(f"Registration failed: {result['error']}")


def _doctor_signin():
    st.subheader("🔐 Doctor Sign In")

    with st.form("doctor_signin_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please enter email and password.")
            return

        result = login_doctor(email, password)
        if result["success"]:
            st.session_state.logged_in = True
            st.session_state.user_role = "doctor"
            st.session_state.doctor_id = result["doctor_id"]
            st.session_state.doctor_name = result["name"]
            st.session_state.doctor_email = result["email"]
            st.session_state.doctor_specialization = result["specialization"]
            
            # ✅ Save to URL so it persists on Page Refresh
            st.query_params["role"] = "doctor"
            st.query_params["uid"] = result["doctor_id"]
            st.rerun()
        else:
            st.error(f"Login failed: {result['error']}")