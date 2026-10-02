"""
Vector store layer shared by the RAG-enabled MCP servers.

Persists two ChromaDB collections on disk:
- drug_library        : curated over-the-counter medication guidance
- medical_records_rag : patient medical records and document excerpts

Embedding strategy:
- If the MiniLM model is present in the local Hugging Face cache (or in
  src/local_models/all-MiniLM-L6-v2/), it is loaded fully offline.
- Otherwise a built-in offline embedder (word + character-trigram hashing)
  is used, so the system never blocks on the network.
"""
import os
import re
import sys
import time
import math
import hashlib
import threading

# Offline-first: the neural model is only ever loaded from the local cache.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from chromadb import PersistentClient

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(SRC_DIR, "chroma_store")

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
_LOCAL_MODEL_DIR = os.path.join(SRC_DIR, "local_models", "all-MiniLM-L6-v2")
_HF_HOME = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
_HF_MODEL_CACHE = os.path.join(_HF_HOME, "hub", "models--sentence-transformers--all-MiniLM-L6-v2")

DRUG_COLLECTION = "drug_library"
RECORDS_COLLECTION = "medical_records_rag"

MATCH_CUTOFF = 0.65

_client = None
_embedding_model = None
_lock = threading.RLock()


def _log(message: str):
    # stderr only — stdout belongs to the MCP stdio protocol in server processes
    print(f"[rag] {message}", file=sys.stderr, flush=True)


class _OfflineFallbackEmbedder:
    """
    Built-in embedder for environments where the neural model is not cached.
    Deterministic, dependency-free, network-free.
    """

    DIMENSIONS = 512
    WORD_WEIGHT = 1.0
    TRIGRAM_WEIGHT = 0.5

    def encode(self, texts, show_progress_bar=False, normalize_embeddings=True):
        return [self._vector(text) for text in texts]

    def _vector(self, text):
        vector = [0.0] * self.DIMENSIONS
        for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
            self._add(vector, "w:" + token, self.WORD_WEIGHT)
            padded = f"^^{token}$$"
            for i in range(len(padded) - 2):
                self._add(vector, "c:" + padded[i:i + 3], self.TRIGRAM_WEIGHT)
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    @staticmethod
    def _add(vector, key, weight):
        index = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % len(vector)
        vector[index] += weight


def _model_available_locally() -> bool:
    return os.path.isdir(_LOCAL_MODEL_DIR) or os.path.isdir(_HF_MODEL_CACHE)


def _get_embedding_model():
    global _embedding_model, MATCH_CUTOFF
    if _embedding_model is None:
        with _lock:
            if _embedding_model is None:
                t0 = time.perf_counter()
                if _model_available_locally():
                    model_path = _LOCAL_MODEL_DIR if os.path.isdir(_LOCAL_MODEL_DIR) else MODEL_ID
                    _log(f"Loading embedding model '{model_path}' from the local cache...")
                    try:
                        from sentence_transformers import SentenceTransformer
                        _embedding_model = SentenceTransformer(model_path)
                        _log(f"Embedding model ready (MiniLM) in {time.perf_counter() - t0:.2f}s")
                    except Exception as e:
                        _log(f"Model could not be loaded ({e}); using the built-in offline embedder.")
                        _embedding_model = _OfflineFallbackEmbedder()
                else:
                    _log("Neural embedding model not cached — using the built-in offline embedder.")
                    _embedding_model = _OfflineFallbackEmbedder()

                if isinstance(_embedding_model, _OfflineFallbackEmbedder):
                    MATCH_CUTOFF = 0.97
    return _embedding_model


def embed_texts(texts: list) -> list:
    model = _get_embedding_model()
    vectors = model.encode(list(texts), show_progress_bar=False, normalize_embeddings=True)
    if hasattr(vectors, "tolist"):
        vectors = vectors.tolist()
    return vectors


def get_client():
    global _client
    if _client is None:
        _client = PersistentClient(path=CHROMA_DIR)
    return _client


def get_collection(name: str):
    return get_client().get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"}
    )


def add_documents(collection_name: str, documents: list, metadatas: list, ids: list) -> int:
    if not documents:
        return 0
    with _lock:
        collection = get_collection(collection_name)
        collection.upsert(
            embeddings=embed_texts(documents),
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
    return len(documents)


def delete_documents(collection_name: str, ids: list) -> int:
    if not ids:
        return 0
    with _lock:
        collection = get_collection(collection_name)
        found = collection.get(ids=ids).get("ids", [])
        if found:
            collection.delete(ids=found)
    return len(found)


def collection_stats() -> dict:
    """Diagnostics: how many vectors are in each collection."""
    stats = {}
    for name in (DRUG_COLLECTION, RECORDS_COLLECTION):
        try:
            stats[name] = get_collection(name).count()
        except Exception as e:
            stats[name] = f"error: {e}"
    return stats


def search_collection(collection_name: str, query: str, n_results: int = 5, where: dict = None) -> list:
    collection = get_collection(collection_name)
    count = collection.count()
    if count == 0:
        _log(f"search_collection('{collection_name}'): collection is EMPTY")
        return []
    kwargs = {
        "query_embeddings": embed_texts([query]),
        "n_results": min(n_results, count),
    }
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    return [
        {
            "id": ids[i],
            "document": documents[i],
            "metadata": metadatas[i] if metadatas else {},
            "distance": distances[i] if distances else 0.0,
        }
        for i in range(len(ids))
    ]


def search_with_cutoff(collection_name: str, query: str, n_results: int = 5, where: dict = None) -> list:
    """
    Semantic search that applies the active relevance cutoff: returns an
    empty list when the best match is not close enough for the embedding
    mode currently in use.
    """
    t0 = time.perf_counter()
    _get_embedding_model()
    hits = search_collection(collection_name, query, n_results=n_results, where=where)
    elapsed = time.perf_counter() - t0
    if hits:
        _log(f"search_with_cutoff('{collection_name}', '{query[:40]}') -> {len(hits)} hits, "
             f"best distance={hits[0]['distance']:.3f} (cutoff={MATCH_CUTOFF}), {elapsed:.2f}s")
        if hits[0]["distance"] > MATCH_CUTOFF:
            _log("  -> all hits rejected by relevance cutoff")
            return []
    else:
        _log(f"search_with_cutoff('{collection_name}', '{query[:40]}') -> 0 hits, {elapsed:.2f}s")
    return hits