"""Chemins, lecture des donnees, tokenisation et chargement paresseux de l'index RAG."""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "data" / "chunks" / "chunks.jsonl"
TEMPLATES = ROOT / "data" / "qa" / "templates.jsonl"
PAIRS = ROOT / "data" / "dataset" / "pairs.jsonl"
TEST = ROOT / "eval" / "test_set.jsonl"
RAG_DIR = ROOT / "data" / "rag"
DOCS = RAG_DIR / "docs.jsonl"
BM25 = RAG_DIR / "bm25.pkl"
EMB = RAG_DIR / "emb.npy"
EMB_IDS = RAG_DIR / "emb_ids.json"
EMB_CACHE = RAG_DIR / "emb_cache.npz"
EMB_CACHE_IDX = RAG_DIR / "emb_cache_index.json"
QUERY_CACHE = RAG_DIR / "query_cache.jsonl"
STOP_FILE = RAG_DIR / "STOP"
REPORT = ROOT / "eval" / "report"

OLLAMA = "http://localhost:11434"
EMBED_MODEL = "qwen3-embedding:0.6b"
QUERY_INSTRUCT = "Given a question about Overwatch, retrieve wiki passages that answer it"

# mots vides : retires de l'index et des requetes BM25 (l'idf s'occupe du reste)
STOPWORDS = set("""a an the of in on at to for and or by with as is are was were be been it its this that these those
there their his her he she they what which who whom whose when where why how do does did can could has have had from
s not no yes""".split())

_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*|[^\W_]+")


def tokenize(text):
    """Minuscules, mots alphanumeriques, nombres decimaux conserves (1.5, 1,500 -> 1500)."""
    out = []
    for t in _TOKEN_RE.findall(text.lower()):
        if t[0].isdigit():
            t = re.sub(r"(?<=\d),(?=\d)", "", t)
        if t in STOPWORDS:
            continue
        out.append(t)
    return out


def sha1(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def read_jsonl(path):
    path = Path(path)
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # derniere ligne eventuellement incomplete
    return out


def page_key(doc):
    """(source, titre) en minuscules ; les fiches de faits forment une « page » a part."""
    k = (doc["source"], doc["title"].lower())
    return k + ("facts",) if doc["id"].startswith("facts:") else k


# ------------------------------------------------------------------ fiches de faits

def is_fact_template(t):
    """Faits absents du texte nettoye : templates sans chunk (infobox sur pages non chunkees) ET
    awards (MVP, prize pools : issus du wikitext brut, le chunk de la page ne les contient pas)."""
    return t.get("chunk_id") is None or t.get("category") == "award"


def build_fact_cards(templates, max_words=300):
    """-> (cartes, map id_template -> id_carte). Une carte regroupe les reponses distinctes d'une page."""
    by_page = defaultdict(list)
    for t in templates:
        if is_fact_template(t):
            _, src, pageid, _n = t["id"].split(":")
            by_page[(src, int(pageid))].append(t)
    cards, tmap = [], {}
    for (src, pageid), ts in sorted(by_page.items()):
        title, revid = ts[0]["title"], ts[0]["revid"]
        groups, cur, words, seen = [], [], 0, set()
        for t in ts:
            a = " ".join(t["answer"].split())
            if a not in seen:
                seen.add(a)
                w = len(a.split())
                if cur and words + w > max_words:
                    groups.append(cur)
                    cur, words = [], 0
                cur.append(a)
                words += w
            t["_ans"] = a
        if cur:
            groups.append(cur)
        index = {}
        for n, g in enumerate(groups):
            for a in g:
                index[a] = n
        for n, g in enumerate(groups):
            cid = f"facts:{src}:{pageid}:{n}"
            cards.append({"id": cid, "revid": revid, "source": src, "title": title, "section": "(facts)",
                          "url": "", "text": f"Page: {title} (facts)\n" + "\n".join(f"- {a}" for a in g)})
        for t in ts:
            tmap[t["id"]] = f"facts:{src}:{pageid}:{index[t['_ans']]}"
            del t["_ans"]
    return cards, tmap


# ------------------------------------------------------------------ index charge a la demande

class Index:
    def __init__(self):
        import pickle
        if not DOCS.exists() or not BM25.exists():
            raise SystemExit("Index RAG absent : lancer `ow-rag index` (python -m rag.cli index --mode bm25)")
        self.docs = read_jsonl(DOCS)
        self.pos = {d["id"]: i for i, d in enumerate(self.docs)}
        with open(BM25, "rb") as f:
            self.bm25 = pickle.load(f)
        self.emb = None
        if EMB.exists() and EMB_IDS.exists():
            import numpy as np
            ids = json.loads(EMB_IDS.read_text(encoding="utf-8"))
            if ids == [d["id"] for d in self.docs]:
                self.emb = np.load(EMB)
            else:
                print("[rag] emb_ids.json ne correspond pas a docs.jsonl : embeddings ignores (relancer `index`)")
