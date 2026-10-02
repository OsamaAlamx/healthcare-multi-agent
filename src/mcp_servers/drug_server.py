"""
MCP Server 4: Drug Library (RAG)
Handles: over-the-counter medication lookup and prescription audit logging

The vector_store import is done lazily inside the tool function so the
subprocess boots fast. A background thread pre-loads the embedding model
at startup so the first real search is fast without the parent process
needing to invoke any tool during warm-up.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("drug-server")


@mcp.tool()
def search_drug_library(condition: str) -> str:
    """
    Semantic search over the curated over-the-counter drug library (RAG).
    Returns matched medications with dose, limits, duration, precautions,
    contraindications, and red-flag advice. Only recommend drugs returned
    by this tool.
    """
    from rag.vector_store import DRUG_COLLECTION, search_with_cutoff

    hits = search_with_cutoff(DRUG_COLLECTION, condition, n_results=4)
    print(f"[drug-server] search_drug_library('{condition}') -> {len(hits)} hits",
          file=sys.stderr, flush=True)
    if hits:
        best = hits[0]
        print(f"[drug-server] best match distance={best['distance']:.3f} "
              f"meta_condition={best['metadata'].get('condition')}",
              file=sys.stderr, flush=True)

    if not hits:
        return (
            "No closely matching over-the-counter guidance was found for this "
            "request. Advise the patient to consult a doctor instead of taking "
            "any medication."
        )

    blocks = []
    for i, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        blocks.append(
            f"MATCH {i}:\n"
            f"  Condition: {meta.get('condition')}\n"
            f"  Drug: {meta.get('drug_name')} ({meta.get('drug_class')})\n"
            f"  Typical dose: {meta.get('typical_dose')}\n"
            f"  Limits: {meta.get('limits')}\n"
            f"  Duration: {meta.get('max_duration')}\n"
            f"  Precautions: {meta.get('precautions')}\n"
            f"  Contraindications: {meta.get('contraindications')}\n"
            f"  See a doctor if: {meta.get('when_to_see_doctor')}"
        )
    return "\n\n".join(blocks)


@mcp.tool()
def log_prescription(patient_email: str, condition: str, drug_name: str,
                     dose: str, duration: str) -> str:
    """
    Records an over-the-counter recommendation given to a patient so the
    suggestion remains auditable.
    """
    from database import get_db
    from models import Patient, PrescriptionLog

    try:
        with get_db() as db:
            patient = db.query(Patient).filter(Patient.email == patient_email).first()
            if not patient:
                return f"ERROR: Patient with email {patient_email} not found."
            db.add(PrescriptionLog(
                patient_id=patient.patient_id,
                patient_email=patient_email,
                condition=condition,
                drug_name=drug_name,
                dose=dose,
                duration=duration
            ))
        return f"SUCCESS: Recommendation recorded for {patient_email}."
    except Exception as e:
        return f"ERROR: {str(e)}"


def _preload_heavy_deps():
    """
    Pre-loads chromadb + the embedding model in a background thread BEFORE
    the server starts answering requests, so the first search_drug_library
    call is fast. Failures are non-fatal — the lazy path still works.
    """
    try:
        from rag.vector_store import _get_embedding_model, DRUG_COLLECTION, search_with_cutoff
        _get_embedding_model()
        search_with_cutoff(DRUG_COLLECTION, "fever high temperature", n_results=1)
        print("[drug-server] warm-up: embedding model + collection ready",
              file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[drug-server] warm-up failed (non-fatal): {e}",
              file=sys.stderr, flush=True)


if __name__ == "__main__":
    import threading
    threading.Thread(target=_preload_heavy_deps, daemon=True, name="drug-preload").start()
    mcp.run(transport="stdio")