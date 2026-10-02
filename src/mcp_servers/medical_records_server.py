"""
MCP Server 1: Medical Records & Documents
Handles: medical history, records, uploaded documents, semantic retrieval
"""
import sys
import time as _t
_T0 = _t.perf_counter()
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from database import get_db
from models import MedicalRecord, Patient, MedicalDocument

mcp = FastMCP("medical-records-server")


@mcp.tool()
def record_medical_record(patient_email: str, record_type: str, details: str) -> str:
    """
    Saves a persistent medical history entry and indexes it for semantic
    retrieval. record_type must be: allergy, chronic_condition, or medication.
    """
    try:
        with get_db() as db:
            patient = db.query(Patient).filter(Patient.email == patient_email).first()
            if not patient:
                return f"ERROR: Patient with email {patient_email} not found."

            superseded = db.query(MedicalRecord).filter(
                MedicalRecord.patient_email == patient_email,
                MedicalRecord.record_type == record_type,
                MedicalRecord.details.ilike(f"%{details}%"),
                MedicalRecord.is_active == True
            ).all()
            superseded_ids = [f"rec_{old.id}" for old in superseded]
            for old in superseded:
                old.is_active = False

            record = MedicalRecord(
                patient_id=patient.patient_id,
                patient_email=patient_email,
                record_type=record_type,
                details=details,
                is_active=True
            )
            db.add(record)
            db.flush()
            record_id = record.id
            patient_id_value = patient.patient_id

        from rag.vector_store import RECORDS_COLLECTION, add_documents, delete_documents

        delete_documents(RECORDS_COLLECTION, superseded_ids)
        add_documents(
            RECORDS_COLLECTION,
            documents=[f"{record_type.replace('_', ' ').title()}: {details}"],
            metadatas=[{
                "patient_id": patient_id_value,
                "source": "record",
                "record_type": record_type,
                "is_active": "true",
            }],
            ids=[f"rec_{record_id}"]
        )
        return f"SUCCESS: {record_type.capitalize()} '{details}' saved for {patient_email}."
    except Exception as e:
        return f"ERROR: {str(e)}"


@mcp.tool()
def fetch_medical_history(patient_email: str) -> str:
    """
    Fetches the patient's active clinical details, medications, and allergies.
    """
    with get_db() as db:
        records = db.query(MedicalRecord).filter(
            MedicalRecord.patient_email == patient_email,
            MedicalRecord.is_active == True
        ).all()

        if not records:
            return "No active medical history found."

        history = {}
        for r in records:
            history.setdefault(r.record_type, []).append(r.details)

        formatted = "\n".join([f"- {k.upper()}: {', '.join(v)}" for k, v in history.items()])
        return f"Medical Records for {patient_email}:\n{formatted}"


@mcp.tool()
def fetch_patient_documents(patient_id: str) -> str:
    """
    Lists all uploaded medical documents for a patient with their extracted text previews.
    Returns document IDs, filenames, types, and first 500 characters of extracted text.
    """
    with get_db() as db:
        docs = db.query(MedicalDocument).filter(
            MedicalDocument.patient_id == patient_id
        ).order_by(MedicalDocument.upload_date.desc()).all()

        if not docs:
            return "No uploaded documents found for this patient."

        results = []
        for doc in docs:
            preview = (doc.extracted_text or "")[:500]
            summary_status = "✅ Summarized" if doc.summary else "❌ Not summarized"
            results.append(
                f"Document ID: {doc.id}\n"
                f"  Filename: {doc.filename}\n"
                f"  Type: {doc.document_type}\n"
                f"  Uploaded: {doc.upload_date.strftime('%Y-%m-%d')}\n"
                f"  Summary: {summary_status}\n"
                f"  Text Preview: {preview}..."
            )
        return "\n\n".join(results)


@mcp.tool()
def get_document_full_text(document_id: int) -> str:
    """
    Retrieves the complete extracted text from a specific uploaded medical document.
    Use this before summarizing a document.
    """
    with get_db() as db:
        doc = db.query(MedicalDocument).filter(
            MedicalDocument.id == document_id
        ).first()

        if not doc:
            return f"ERROR: Document with ID {document_id} not found."

        if not doc.extracted_text:
            return f"ERROR: No text could be extracted from {doc.filename}."

        return (
            f"Document: {doc.filename}\n"
            f"Type: {doc.document_type}\n"
            f"Full Text:\n{doc.extracted_text}"
        )


@mcp.tool()
def save_document_summary(document_id: int, summary: str) -> str:
    """
    Saves a generated summary for a medical document so it doesn't need to be re-summarized.
    """
    try:
        with get_db() as db:
            doc = db.query(MedicalDocument).filter(
                MedicalDocument.id == document_id
            ).first()
            if not doc:
                return f"ERROR: Document {document_id} not found."
            doc.summary = summary
        return f"SUCCESS: Summary saved for document {document_id}."
    except Exception as e:
        return f"ERROR: {str(e)}"


@mcp.tool()
def search_medical_records(patient_id: str, query: str) -> str:
    """
    Semantic (RAG) search across a patient's active medical records and
    uploaded document excerpts. Accepts natural-language queries such as
    "allergies", "current medications", or "lab findings". Intended for
    clinician review.
    """
    from rag.vector_store import RECORDS_COLLECTION, search_collection

    hits = search_collection(
        RECORDS_COLLECTION, query, n_results=6, where={"patient_id": patient_id}
    )
    if not hits:
        return "No semantically matching records found for this patient."

    blocks = []
    for hit in hits:
        meta = hit["metadata"]
        if meta.get("source") == "record":
            label = f"[{meta.get('record_type', 'record').upper()} RECORD]"
        else:
            label = f"[DOCUMENT: {meta.get('filename', 'document')}]"
        blocks.append(f"{label} {hit['document']}")

    return f'RAG results for "{query}" (top {len(hits)}):\n\n' + "\n\n".join(blocks)


if __name__ == "__main__":
    import sys as _sys
    print(f"[server] clinical-server ready in {_t.perf_counter() - _T0:.2f}s", file=_sys.stderr, flush=True)
    mcp.run(transport="stdio")