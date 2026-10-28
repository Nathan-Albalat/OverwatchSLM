"""retrieve(question, k) : recherche hybride BM25 + dense (RRF). Signature attendue par bench/run.py."""
import re
import unicodedata

import numpy as np

from rag import common as C

K_RRF = 60
POOL = 50          # candidats gardes par ranker avant fusion
MAX_PER_PAGE = 2   # diversification : au plus N passages de la meme page

_state = {"index": None, "encoder": None, "warned": set()}


def _warn(msg):
    if msg not in _state["warned"]:
        _state["warned"].add(msg)
        print(f"[rag] {msg}")


def get_index():
    if _state["index"] is None:
        _state["index"] = C.Index()
    return _state["index"]


def resolve_mode(mode, ix):
    """Mode effectif : repli explicite sur bm25 si l'index d'embeddings est absent."""
    mode = mode or "hybrid"
    if mode not in ("bm25", "dense", "hybrid"):
        raise ValueError(f"mode inconnu: {mode}")
    if mode != "bm25" and ix.emb is None:
        _warn(f"index d'embeddings absent (emb.npy) : repli sur bm25 au lieu de '{mode}' "
              f"(lancer `ow-rag index --mode hybrid` pour les calculer)")
        return "bm25"
    return mode


def _dense(question, ix, n):
    if _state["encoder"] is None:
        from rag.embed import QueryEncoder
        _state["encoder"] = QueryEncoder()
    q = _state["encoder"].encode(question)
    s = ix.emb @ q
    idx = np.argpartition(-s, n)[:n]
    idx = idx[np.argsort(-s[idx])]
    return [(int(i), float(s[i])) for i in idx]


def retrieve(question, k=5, mode=None, exclude_ids=(), max_per_page=MAX_PER_PAGE, entity=False):
    ix = get_index()
    mode = resolve_mode(mode, ix)
    excl = set(exclude_ids)
    pool = POOL + len(excl)
    lists = []
    if mode in ("bm25", "hybrid"):
        lists.append(ix.bm25.top(question, pool))
    if mode in ("dense", "hybrid"):
        lists.append(_dense(question, ix, pool))
    if len(lists) == 1:
        ranked = lists[0]
    else:
        fused = {}
        for lst in lists:
            for rank, (i, _) in enumerate(lst):
                fused[i] = fused.get(i, 0.0) + 1.0 / (K_RRF + rank + 1)
        ranked = sorted(fused.items(), key=lambda x: -x[1])
    out, per_page = [], {}
    for i, sc in ranked:
        d = ix.docs[i]
        if d["id"] in excl:
            continue
        pk = C.page_key(d)
        if max_per_page and per_page.get(pk, 0) >= max_per_page:
            continue
        per_page[pk] = per_page.get(pk, 0) + 1
        out.append({"id": d["id"], "title": d["title"], "section": d["section"], "source": d["source"],
                    "text": d["text"], "score": round(sc, 5)})
        if len(out) >= k:
            break
    if entity:
        out = _with_entity_cards(question, ix, out, k, excl, mode=entity)
    return out


# ------------------------------------------------------------------ fiches des entites citees (v2 de la recherche)

def _norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " " + re.sub(r"[^a-z0-9]+", " ", s).strip() + " "


def _entities(ix):
    """Pages Fandom d'entites (heros, personnages, lieux et cartes) : titre normalise -> position de leur fiche
    (chunk 0, qui porte l'infobox : nationalite, vrai nom, role, localisation...)."""
    if "entities" not in _state:
        ent = {}
        for i, d in enumerate(ix.docs):
            if d["source"] != "fandom" or not d["id"].endswith(":0") or "/" in d["title"]:
                continue
            head = d["text"][:1500]
            if "\nName: " in head and ("[Game info]" in head or "[Background]" in head
                                       or re.search(r"\nLocation: ", head)):
                t = _norm(d["title"])
                if len(t.strip()) >= 3:
                    ent[t] = i
        _state["entities"] = ent
    return _state["entities"]


def _with_entity_cards(question, ix, out, k, excl, mode=True, max_cards=2):
    """Si la question nomme une entite, sa fiche entre dans les passages (en tete), a nombre de passages constant :
    les questions d'attribut (« What country is Sigma from? ») ratent sinon la fiche, mal classee par BM25 et
    les embeddings (« country » != « Nationality », bloc de champs peu « semantique »)."""
    q = _norm(question)
    found = sorted((t for t in _entities(ix) if t in q), key=len, reverse=True)
    cards, seen = [], {p["id"] for p in out}
    for t in found:
        if any(t in c_t for c_t, _ in cards):      # « Soldier 76 » plutot que « Soldier » (titre englobe)
            continue
        d = ix.docs[_entities(ix)[t]]
        if d["id"] not in excl:
            cards.append((t, d))
        if len(cards) >= max_cards:
            break
    new = [{"id": d["id"], "title": d["title"], "section": d["section"], "source": d["source"],
            "text": d["text"], "score": None} for _, d in cards if d["id"] not in seen]
    if not new:
        return out
    # entity="add" : la fiche s'ajoute (k + 1 ou 2 passages) ; sinon elle remplace le dernier passage
    return new + out if mode == "add" else (new + out)[:k]
