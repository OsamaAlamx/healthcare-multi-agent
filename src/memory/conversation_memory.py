from database import get_db
from models import ConversationHistory
from langchain_core.messages import HumanMessage, AIMessage


def save_message(patient_id: str, role: str, content: str, agent_name: str = None):
    with get_db() as db:
        db.add(ConversationHistory(
            patient_id=patient_id,
            role=role,
            content=content,
            agent_name=agent_name
        ))


def load_conversation(patient_id: str, limit: int = 20) -> list:
    with get_db() as db:
        rows = (
            db.query(ConversationHistory)
            .filter(ConversationHistory.patient_id == patient_id)
            .order_by(ConversationHistory.timestamp.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        messages = []
        for row in rows:
            if row.role == "user":
                messages.append(HumanMessage(content=row.content))
            elif row.role == "assistant":
                messages.append(AIMessage(content=row.content))
        return messages


def load_conversation_display(patient_id: str, limit: int = 50) -> list:
    with get_db() as db:
        rows = (
            db.query(ConversationHistory)
            .filter(ConversationHistory.patient_id == patient_id)
            .order_by(ConversationHistory.timestamp.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [
            {"role": r.role, "content": r.content, "agent_name": r.agent_name}
            for r in rows
        ]


def clear_conversation(patient_id: str):
    with get_db() as db:
        db.query(ConversationHistory).filter(
            ConversationHistory.patient_id == patient_id
        ).delete()