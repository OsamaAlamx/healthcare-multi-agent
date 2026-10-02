from database import get_db
from models import EpisodicMemory


def store_episodic_memory(patient_id: str, memory_type: str, content: str, context: str = None):
    with get_db() as db:
        existing = db.query(EpisodicMemory).filter(
            EpisodicMemory.patient_id == patient_id,
            EpisodicMemory.memory_type == memory_type,
            EpisodicMemory.content.ilike(f"%{content}%"),
            EpisodicMemory.is_active == True
        ).first()

        if existing:
            return f"Already recorded: {content}"

        db.add(EpisodicMemory(
            patient_id=patient_id,
            memory_type=memory_type,
            content=content,
            context=context,
            is_active=True
        ))
        return f"Stored {memory_type}: {content}"


def retrieve_episodic_memories(patient_id: str, memory_type: str = None) -> list:
    with get_db() as db:
        query = db.query(EpisodicMemory).filter(
            EpisodicMemory.patient_id == patient_id,
            EpisodicMemory.is_active == True
        )
        if memory_type:
            query = query.filter(EpisodicMemory.memory_type == memory_type)
        memories = query.order_by(EpisodicMemory.timestamp.desc()).all()
        return [
            {
                "type": m.memory_type,
                "content": m.content,
                "context": m.context,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None
            }
            for m in memories
        ]


def format_episodic_context(patient_id: str) -> str:
    memories = retrieve_episodic_memories(patient_id)
    if not memories:
        return ""
    lines = ["KNOWN PATIENT INFORMATION (from episodic memory):"]
    for m in memories:
        lines.append(f"- {m['type'].upper()}: {m['content']}")
    return "\n".join(lines)