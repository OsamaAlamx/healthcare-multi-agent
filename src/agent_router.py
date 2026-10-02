"""
The Brain: LangGraph StateGraph routing patient messages to agents.

Graph: router -> (receptionist | reasoning | memory | prescriber) -> END

The Doctor Summary agent is deliberately NOT part of this graph — it is
triggered manually from the Doctor Dashboard via doctor_summary_service.py,
which keeps it unreachable from any patient message.

Every message passes through input guardrails before routing, and every
agent response passes through output guardrails before it is stored.
"""
import time
from typing import TypedDict, Annotated

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from agents.agent_factory import (
    _get_llm,
    make_receptionist_factory,
    make_reasoning_factory,
    make_memory_factory,
    make_prescriber_factory,
    detect_and_store_allergies,
)
from mcp_client import run_agent_with_mcp
from memory.conversation_memory import save_message, load_conversation_display
from guardrails.input_guardrails import apply_input_guardrails
from guardrails.output_guardrails import apply_output_guardrails
from perf_log import timer, new_request_id, logger as perf_logger

AGENT_DISPLAY_NAMES = {
    "receptionist": "Receptionist",
    "reasoning": "Reasoning",
    "memory": "Memory",
    "prescriber": "Prescriber",
}

INTENT_TAB_INDEX = {
    "receptionist": 0,
    "reasoning": 1,
    "memory": 2,
    "prescriber": 3,
}


def get_tab_index(intent: str) -> int:
    """Maps an agent intent to the patient dashboard tab index."""
    return INTENT_TAB_INDEX.get(intent, 0)


ROUTER_PROMPT = """You are an intent classifier for a medical AI system.
Classify the user's message into EXACTLY ONE category:
- "reasoning"    - symptoms, pain, illness, health concerns, triage
- "memory"       - allergies, medications, chronic conditions, medical history
- "receptionist" - booking appointments, finding doctors, scheduling
- "prescriber"   - asking what medicine or over-the-counter remedy to take
PRIORITY RULES:
- If symptoms are mentioned together with a request for medicine, choose "prescriber".
- If symptoms sound severe or urgent (chest pain, breathing trouble, stroke
  signs, bleeding, unconsciousness), ALWAYS choose "reasoning" (safety first).
- A plain symptom description without a medicine request goes to "reasoning".
Respond with ONLY the category name in lowercase."""


def classify_intent(text: str) -> str:
    try:
        with timer("router LLM call", ""):
            response = _get_llm().invoke(
                [SystemMessage(content=ROUTER_PROMPT), HumanMessage(content=text)]
            )
        intent = response.content.strip().lower().strip("\"'")
        if intent in ("receptionist", "reasoning", "memory", "prescriber"):
            return intent
    except Exception:
        pass
    return _fallback_keyword_classify(text)


def _fallback_keyword_classify(text: str) -> str:
    text = text.lower()

    prescriber_keywords = [
        "what should i take", "what can i take", "any medicine", "medicine for",
        "medication for", "something for", "otc", "prescribe", "drug for",
        "tablet for", "pill for", "remedy", "dose",
    ]
    for kw in prescriber_keywords:
        if kw in text:
            return "prescriber"

    receptionist_keywords = [
        "book", "appointment", "schedule", "reschedule",
        "available doctor", "doctor available",
    ]
    for kw in receptionist_keywords:
        if kw in text:
            return "receptionist"

    memory_keywords = [
        "allergic", "allergy", "i take", "i'm taking", "im taking",
        "diagnosed", "my condition", "chronic",
    ]
    for kw in memory_keywords:
        if kw in text:
            return "memory"

    return "reasoning"


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    patient_id: str
    patient_name: str
    patient_email: str
    next_agent: str


def router_node(state: AgentState):
    intent = state.get("next_agent") or classify_intent(state["messages"][-1].content)
    return {"next_agent": intent}


def route_to_agent(state: AgentState) -> str:
    return state["next_agent"]


def receptionist_node(state: AgentState):
    factory = make_receptionist_factory(state["patient_id"], state["patient_name"], state["patient_email"])
    result = run_agent_with_mcp("receptionist", factory, state["messages"])
    return {"messages": [result["messages"][-1]]}


def reasoning_node(state: AgentState):
    factory = make_reasoning_factory(state["patient_id"], state["patient_name"], state["patient_email"])
    result = run_agent_with_mcp("reasoning", factory, state["messages"])
    return {"messages": [result["messages"][-1]]}


def memory_node(state: AgentState):
    factory = make_memory_factory(state["patient_id"], state["patient_name"], state["patient_email"])
    result = run_agent_with_mcp("memory", factory, state["messages"])
    return {"messages": [result["messages"][-1]]}


def prescriber_node(state: AgentState):
    """
    Safety-critical pre-steps (triage + medical history) are deterministic,
    so they are executed directly here instead of trusting the LLM to call
    them. This removes 2 LLM round-trips AND guarantees the safety workflow
    always runs.
    """
    from mcp_servers.clinical_server import clinical_triage
    from mcp_servers.medical_records_server import fetch_medical_history

    last_user_msg = state["messages"][-1].content

    with timer("prescriber pre-fetch (triage + history)", ""):
        triage = clinical_triage(last_user_msg)
        history = fetch_medical_history(state["patient_email"])
    perf_logger.info(f"      TRIAGE: {triage.splitlines()[0] if triage else 'n/a'}")
    perf_logger.info(f"      HISTORY: {history[:120]}")

    context_msg = HumanMessage(
        content=(
            "[SYSTEM PRE-FETCHED DATA — these steps are already completed for you. "
            "Do NOT call clinical_triage or fetch_medical_history again.]\n\n"
            f"TRIAGE RESULT:\n{triage}\n\n"
            f"MEDICAL HISTORY:\n{history}\n\n"
            "Using ONLY the data above plus search_drug_library, produce your "
            "recommendation following the safety rules in your instructions."
        )
    )

    factory = make_prescriber_factory(
        state["patient_id"], state["patient_name"], state["patient_email"]
    )
    result = run_agent_with_mcp("prescriber", factory, state["messages"] + [context_msg])
    return {"messages": [result["messages"][-1]]}


graph = StateGraph(AgentState)
graph.add_node("router", router_node)
graph.add_node("receptionist", receptionist_node)
graph.add_node("reasoning", reasoning_node)
graph.add_node("memory", memory_node)
graph.add_node("prescriber", prescriber_node)

graph.set_entry_point("router")
graph.add_conditional_edges("router", route_to_agent, {
    "receptionist": "receptionist",
    "reasoning": "reasoning",
    "memory": "memory",
    "prescriber": "prescriber",
})
for node in ("receptionist", "reasoning", "memory", "prescriber"):
    graph.add_edge(node, END)

MEDICAL_GRAPH = graph.compile()


def _load_agent_history(patient_id: str, agent_name: str, limit: int = 10) -> list:
    """Loads the recent conversation for one agent only, so each agent sees
    its own exchanges and never another agent's small talk."""
    rows = load_conversation_display(patient_id, limit=50)
    selected = []
    for row in reversed(rows):
        if row["role"] == "user":
            selected.append(HumanMessage(content=row["content"]))
        elif row.get("agent_name") == agent_name:
            selected.append(AIMessage(content=row["content"]))
        if len(selected) >= limit:
            break
    selected.reverse()
    return selected


def handle_patient_query(patient_id: str, patient_name: str, patient_email: str, user_message: str) -> dict:
    """
    Full pipeline for one patient message:
    input guardrails -> allergy capture -> intent -> per-agent history ->
    LangGraph invocation -> output guardrails -> persistence.
    """
    req = new_request_id()
    t_total = time.perf_counter()
    perf_logger.info(f"[{req}] ========== NEW REQUEST: '{user_message[:60]}' ==========")

    with timer("input_guardrails", req):
        guard = apply_input_guardrails(user_message, patient_id=patient_id)
    if not guard["allowed"]:
        refusal = guard["message"]
        save_message(patient_id, "user", user_message)
        save_message(patient_id, "assistant", refusal, agent_name="System")
        perf_logger.info(f"[{req}] TOTAL: {time.perf_counter() - t_total:.2f}s (blocked)")
        return {
            "response": refusal,
            "agent_name": "System",
            "intent": "receptionist",
            "tab_index": 0,
        }

    user_message = guard["message"]
    emergency = guard["flags"].get("emergency", False)

    with timer("allergy_capture", req):
        detect_and_store_allergies(patient_id, user_message)

    with timer("classify_intent", req):
        intent = classify_intent(user_message)
    if emergency and intent != "reasoning":
        intent = "reasoning"

    agent_name = AGENT_DISPLAY_NAMES[intent]
    with timer("load_agent_history", req):
        messages = _load_agent_history(patient_id, agent_name) + [HumanMessage(content=user_message)]

    save_message(patient_id, "user", user_message)

    state = {
        "messages": messages,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "patient_email": patient_email,
        "next_agent": intent,
    }
    with timer(f"AGENT '{intent}'", req):
        result = MEDICAL_GRAPH.invoke(state)
    agent_reply = result["messages"][-1].content

    with timer("output_guardrails", req):
        output_guard = apply_output_guardrails(
            agent_reply,
            agent_name,
            patient_email=patient_email,
            emergency_input=emergency,
            patient_id=patient_id,
        )

    save_message(patient_id, "assistant", output_guard["response"], agent_name=agent_name)

    perf_logger.info(
        f"[{req}] TOTAL REQUEST: {time.perf_counter() - t_total:.2f}s — intent={intent}"
    )
    return {
        "response": output_guard["response"],
        "agent_name": agent_name,
        "intent": intent,
        "tab_index": INTENT_TAB_INDEX[intent],
    }