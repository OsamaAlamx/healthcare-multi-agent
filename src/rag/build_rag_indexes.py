"""
Builds and refreshes the on-disk RAG indexes.

- drug_library index: loaded once from the curated knowledge base
- medical_records_rag index: backfilled from the relational database, then
  kept up to date by the MCP tools and the document upload flow

All writes are idempotent upserts with deterministic ids, so calling
ensure_indexes() repeatedly is safe.

Standalone usage (from src/):
    python rag/build_rag_indexes.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _log(message: str):
    # stderr only — this module is imported by the app process as well
    print(f"[rag] {message}", file=sys.stderr, flush=True)


from database import get_db
from models import MedicalRecord, MedicalDocument
from rag.drug_library import DRUG_LIBRARY
from rag.vector_store import (
    DRUG_COLLECTION,
    RECORDS_COLLECTION,
    add_documents,
    get_collection,
)


def _format_drug_entry(entry: dict) -> str:
    return (
        f"Condition: {entry['condition']}. Symptoms: {entry['symptoms']}. "
        f"Medication: {entry['drug_name']} ({entry['drug_class']}). "
        f"Typical dose: {entry['typical_dose']}. Limits: {entry['limits']}. "
        f"Duration: {entry['max_duration']}. "
        f"Precautions: {entry['precautions']}. "
        f"Contraindications: {entry['contraindications']}. "
        f"See a doctor if: {entry['when_to_see_doctor']}."
    )


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list:
    if not text or text.startswith("[No extractable text"):
        return []
    text = " ".join(text.split())
    chunks = []
    step = size - overlap
    for start in range(0, len(text), step):
        chunk = text[start:start + size].strip()
        if chunk:
            chunks.append(chunk)
        if start + size >= len(text):
            break
    return chunks


def ensure_drug_library_index() -> int:
    collection = get_collection(DRUG_COLLECTION)
    if collection.count() >= len(DRUG_LIBRARY):
        return 0
    documents, metadatas, ids = [], [], []
    for i, entry in enumerate(DRUG_LIBRARY, start=1):
        documents.append(_format_drug_entry(entry))
        metadatas.append({
            "condition": entry["condition"],
            "drug_name": entry["drug_name"],
            "drug_class": entry["drug_class"],
            "typical_dose": entry["typical_dose"],
            "limits": entry["limits"],
            "max_duration": entry["max_duration"],
            "precautions": entry["precautions"],
            "contraindications": entry["contraindications"],
            "when_to_see_doctor": entry["when_to_see_doctor"],
            "source": "drug_library",
        })
        ids.append(f"drug_{i}")
    _log(f"Indexing {len(DRUG_LIBRARY)} drug library entries...")
    return add_documents(DRUG_COLLECTION, documents, metadatas, ids)


def ingest_document(doc_id: int, patient_id: str, filename: str,
                    document_type: str, extracted_text: str) -> int:
    chunks = chunk_text(extracted_text or "")
    if not chunks:
        return 0
    metadatas = [
        {
            "patient_id": patient_id,
            "source": "document",
            "filename": filename,
            "document_type": document_type or "report",
        }
        for _ in chunks
    ]
    ids = [f"doc_{doc_id}_c{i}" for i in range(len(chunks))]
    _log(f"Indexing document {filename} ({len(chunks)} chunks)...")
    return add_documents(RECORDS_COLLECTION, chunks, metadatas, ids)


def backfill_medical_records() -> int:
    documents, metadatas, ids = [], [], []
    with get_db() as db:
        records = db.query(MedicalRecord).filter(MedicalRecord.is_active == True).all()
        record_count = len(records)
        for rec in records:
            documents.append(f"{rec.record_type.replace('_', ' ').title()}: {rec.details}")
            metadatas.append({
                "patient_id": rec.patient_id,
                "source": "record",
                "record_type": rec.record_type,
                "is_active": "true",
            })
            ids.append(f"rec_{rec.id}")

        docs = db.query(MedicalDocument).all()
        document_chunk_total = 0
        for doc in docs:
            chunks = chunk_text(doc.extracted_text or "")
            document_chunk_total += len(chunks)
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({
                    "patient_id": doc.patient_id,
                    "source": "document",
                    "filename": doc.filename,
                    "document_type": doc.document_type or "report",
                })
                ids.append(f"doc_{doc.id}_c{i}")

    if not ids:
        _log("Nothing to backfill: no active records and no documents with text yet.")
        return 0

    _log(
        f"Backfilling RAG index: {record_count} medical records + "
        f"{document_chunk_total} document chunks..."
    )
    return add_documents(RECORDS_COLLECTION, documents, metadatas, ids)


def ensure_indexes():
    ensure_drug_library_index()
    backfill_medical_records()


if __name__ == "__main__":
    print("Building RAG indexes...", flush=True)
    print("Step 1/2: drug library index", flush=True)
    ensure_drug_library_index()
    print("Step 2/2: medical records + uploaded documents index", flush=True)
    backfill_medical_records()
    print(f"drug_library entries:        {get_collection(DRUG_COLLECTION).count()}")
    print(f"medical_records_rag entries: {get_collection(RECORDS_COLLECTION).count()}")
    print("Done. RAG indexes are ready.", flush=True)