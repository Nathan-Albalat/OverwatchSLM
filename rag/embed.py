"""Embeddings via Ollama (/api/embed). Utilise le GPU : ne pas lancer si il est occupe."""
import json
import numpy as np
import requests

from rag.common import EMBED_MODEL, OLLAMA, QUERY_CACHE, QUERY_INSTRUCT, RAG_DIR, sha1


def embed_texts(texts, model=EMBED_MODEL, truncate=True, timeout=300):
    """texts -> ndarray float32 (n, dim), normalise L2. Corps : {"model", "input": [...]} -> {"embeddings": [[...]]}."""
    body = {"model": model, "input": list(texts), "truncate": bool(truncate), "keep_alive": "10m"}
    r = requests.post(f"{OLLAMA}/api/embed", json=body, timeout=timeout)
    r.raise_for_status()
    v = np.asarray(r.json()["embeddings"], dtype=np.float32)
    if v.ndim != 2 or len(v) != len(texts):
        raise ValueError(f"reponse /api/embed inattendue: forme {v.shape} pour {len(texts)} textes")
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


def query_text(question):
    return f"Instruct: {QUERY_INSTRUCT}\nQuery: {question}"


class QueryEncoder:
    """Embeddings de requetes avec cache memoire + disque (query_cache.jsonl, append)."""

    def __init__(self, model=EMBED_MODEL):
        self.model = model
        self.mem = {}
        if QUERY_CACHE.exists():
            with open(QUERY_CACHE, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("model") == model:
                        self.mem[r["h"]] = np.asarray(r["v"], dtype=np.float32)

    def encode(self, question):
        h = sha1(question)
        if h not in self.mem:
            v = embed_texts([query_text(question)], self.model)[0]
            self.mem[h] = v
            RAG_DIR.mkdir(parents=True, exist_ok=True)
            with open(QUERY_CACHE, "a", encoding="utf-8") as f:
                f.write(json.dumps({"model": self.model, "h": h, "v": [round(float(x), 6) for x in v]}) + "\n")
        return self.mem[h]
