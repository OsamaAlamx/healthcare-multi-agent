import os
import re
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage

from agents.prompts.receptionist_prompt import RECEPTIONIST_PROMPT_TEMPLATE
from agents.prompts.memory_prompt import MEMORY_PROMPT_TEMPLATE
from agents.prompts.reasoning_prompt import REASONING_PROMPT_TEMPLATE
from agents.prompts.doctor_summary_prompt import DOCTOR_SUMMARY_PROMPT_TEMPLATE
from agents.prompts.prescriber_prompt import PRESCRIBER_PROMPT_TEMPLATE

from memory.episodic_memory import format_episodic_context, store_episodic_memory

load_dotenv()


def _get_llm():
    return ChatGroq(
        model=os.getenv("GROQ_MODEL","openai/gpt-oss-120b"),
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
        max_tokens=900,
        max_retries=3,
    )


def _build_prompt(template: str, patient_id: str, patient_name: str, patient_email: str) -> SystemMessage:
    episodic_context = format_episodic_context(patient_id)
    text = template.format(
        patient_name=patient_name,
        patient_email=patient_email,
        patient_id=patient_id,
        episodic_context=episodic_context
    )
    return SystemMessage(content=text)


def make_receptionist_factory(patient_id: str, patient_name: str, patient_email: str):
    """Returns a function that creates a receptionist agent with given tools."""
    prompt = _build_prompt(RECEPTIONIST_PROMPT_TEMPLATE, patient_id, patient_name, patient_email)

    def factory(tools):
        return create_react_agent(model=_get_llm(), tools=tools, prompt=prompt)

    return factory


def make_reasoning_factory(patient_id: str, patient_name: str, patient_email: str):
    prompt = _build_prompt(REASONING_PROMPT_TEMPLATE, patient_id, patient_name, patient_email)

    def factory(tools):
        return create_react_agent(model=_get_llm(), tools=tools, prompt=prompt)

    return factory


def make_memory_factory(patient_id: str, patient_name: str, patient_email: str):
    prompt = _build_prompt(MEMORY_PROMPT_TEMPLATE, patient_id, patient_name, patient_email)

    def factory(tools):
        return create_react_agent(model=_get_llm(), tools=tools, prompt=prompt)

    return factory


def make_prescriber_factory(patient_id: str, patient_name: str, patient_email: str):
    """Returns a factory for the OTC drug recommendation agent."""
    prompt = _build_prompt(PRESCRIBER_PROMPT_TEMPLATE, patient_id, patient_name, patient_email)

    def factory(tools):
        return create_react_agent(model=_get_llm(), tools=tools, prompt=prompt)

    return factory


def make_doctor_summary_factory(patient_id: str, patient_name: str, patient_email: str):
    """Returns a factory for the doctor-facing clinical summary agent."""
    prompt = _build_prompt(DOCTOR_SUMMARY_PROMPT_TEMPLATE, patient_id, patient_name, patient_email)

    def factory(tools):
        return create_react_agent(model=_get_llm(), tools=tools, prompt=prompt)

    return factory


def detect_and_store_allergies(patient_id: str, user_message: str):
    text = user_message.lower()
    allergy_keywords = ["allergic to", "allergy to", "i'm allergic", "i am allergic", "have allergy"]

    for kw in allergy_keywords:
        if kw in text:
            start = text.index(kw) + len(kw)
            remainder = text[start:].strip()
            match = re.match(
                r"^([a-z0-9\s\-]+?)(?:\s+and\s|\s+but\s|\s+also\s|\s+which\s|\s+that\s|[,.\!;\?]|$)",
                remainder
            )
            allergen = match.group(1).strip() if match else remainder[:50].strip()
            if allergen and 1 < len(allergen) < 50:
                store_episodic_memory(
                    patient_id=patient_id,
                    memory_type="allergy",
                    content=allergen,
                    context=user_message
                )
                return allergen
    return None