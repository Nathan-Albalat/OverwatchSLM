"""ow-rag index : docs.jsonl (chunks + fiches de faits), bm25.pkl, emb.npy (+ cache d'embeddings reprenable)."""
import json
import os
import pickle
import time

import numpy as np
import requests
from tqdm import tqdm

from rag import common as C
from rag.bm25 import BM25
from rag.embed import embed_texts


def build_docs():
    chunks = [c for c in C.read_jsonl(C.CHUNKS) if c.get("text", "").strip()]
    docs = [{k: c.get(k, "") for k in ("id", "revid", "source", "title", "section", "url", "text")} for c in chunks]
    cards, _ = C.build_fact_cards(C.read_jsonl(C.TEMPLATES))
    return docs + cards, len(chunks), len(cards)


def _load_cache(model):
    if C.EMB_CACHE.exists() and C.EMB_CACHE_IDX.exists():
        meta = json.loads(C.EMB_CACHE_IDX.read_text(encoding="utf-8"))
        if meta.get("model") == model:
            return {k: i for i, k in enumerate(meta["keys"])}, list(np.load(C.EMB_CACHE)["vecs"])
        print(f"[rag] cache d'embeddings d'un autre modele ({meta.get('model')}) : ignore")
    return {}, []


def _save_cache(model, keys, vecs):
    tmp = C.RAG_DIR / "emb_cache_tmp.npz"
    np.savez(tmp, vecs=np.asarray(vecs, dtype=np.float32))
    os.replace(tmp, C.EMB_CACHE)
    C.EMB_CACHE_IDX.write_text(json.dumps({"model": model, "keys": keys}), encoding="utf-8")


def encode_docs(docs, model, batch, max_words, truncate):
    """Encode les docs absents du cache (cle = sha1 du texte tronque). -> (matrice | None, n_encodes, n_cache)."""
    index, vecs = _load_cache(model)
    keys = list(index)
    texts = [" ".join(d["text"].split(" ")[:max_words]) if max_words else d["text"] for d in docs]
    hashes = [C.sha1(t) for t in texts]
    todo, seen = [], set()
    for i, h in enumerate(hashes):
        if h not in index and h not in seen:
            seen.add(h)
            todo.append(i)
    n_cache = len(docs) - len(todo)
    print(f"{len(docs)} docs, {n_cache} repris du cache, {len(todo)} a encoder (modele {model})")
    stop, last_save, n_enc = None, 0, 0
    bar = tqdm(range(0, len(todo), batch), unit="lot", disable=not todo)
    try:
        for s in bar:
            if C.STOP_FILE.exists():
                stop = "fichier STOP"
                break
            sel = todo[s:s + batch]
            try:
                v = embed_texts([texts[i] for i in sel], model, truncate)
            except (requests.RequestException, ValueError, KeyError) as e:
                stop = f"erreur Ollama: {type(e).__name__}: {e}"
                break
            for i, row in zip(sel, v):
                index[hashes[i]] = len(vecs)
                keys.append(hashes[i])
                vecs.append(row)
            n_enc += len(sel)
            if n_enc - last_save >= 20 * batch:  # flush periodique (reprise apres veille)
                _save_cache(model, keys, vecs)
                last_save = n_enc
    except KeyboardInterrupt:
        stop = "ctrl-c"
    finally:
        bar.close()
    if n_enc > last_save:
        _save_cache(model, keys, vecs)
    if stop:
        print(f"Arret: {stop}. {n_enc} encodes ({len(todo) - n_enc} restants) : relancer la meme commande pour reprendre.")
        return None, n_enc, n_cache
    mat = np.stack([vecs[index[h]] for h in hashes]).astype(np.float32)
    return mat, n_enc, n_cache


def run(mode="hybrid", model=C.EMBED_MODEL, batch=32, max_words=450, truncate=True):
    t0 = time.time()
    C.RAG_DIR.mkdir(parents=True, exist_ok=True)
    docs, n_chunks, n_cards = build_docs()
    tmp = C.DOCS.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    os.replace(tmp, C.DOCS)
    print(f"docs: {len(docs)} = {n_chunks} chunks + {n_cards} fiches de faits -> {C.DOCS}")
    t1 = time.time()
    bm = BM25([d["text"] for d in docs])
    with open(C.BM25, "wb") as f:
        pickle.dump(bm, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"bm25: {len(bm.post)} termes, avgdl {bm.avgdl:.0f} tokens, {time.time() - t1:.1f} s")
    if mode == "bm25":
        # des embeddings obsoletes ne doivent pas etre appaires a un nouveau docs.jsonl
        for p in (C.EMB, C.EMB_IDS):
            if p.exists():
                p.unlink()
        print(f"Termine en {time.time() - t0:.1f} s (bm25 seul)")
        return
    t2 = time.time()
    mat, n_enc, n_cache = encode_docs(docs, model, batch, max_words, truncate)
    if mat is None:
        return
    np.save(C.EMB, mat)
    C.EMB_IDS.write_text(json.dumps([d["id"] for d in docs]), encoding="utf-8")
    print(f"embeddings: {n_enc} encodes, {n_cache} repris du cache, {time.time() - t2:.1f} s (dim {mat.shape[1]}) "
          f"| total {time.time() - t0:.1f} s")
