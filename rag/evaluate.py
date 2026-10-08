"""ow-rag eval : qualite de la recherche sans LLM (hit@k sur le test et sur des paires de validation)."""
import random
import time
from collections import defaultdict

from tqdm import tqdm

from rag import common as C
from rag.retrieve import get_index, resolve_mode, retrieve


def expected_pages(source):
    """'fandom:Anran;Domina' -> {(fandom, anran), (fandom, domina)} ; 'liquipedia:X/2016;2017' -> X/2016, X/2017."""
    if not source or source == "none" or ":" not in source:
        return set()
    src, rest = source.split(":", 1)
    parts = [p.strip() for p in rest.split(";") if p.strip()]
    out = set()
    for j, p in enumerate(parts):
        if j and p.replace("/", "").isdigit() and "/" in parts[0]:
            p = parts[0].rsplit("/", 1)[0] + "/" + p
        out.add((src, p.lower()))
    return out


def _hit_rank(results, pred):
    for r, p in enumerate(results, 1):
        if pred(p):
            return r
    return None


def _pct(ranks, k):
    return 100.0 * sum(1 for r in ranks if r is not None and r <= k) / max(1, len(ranks))


def run(mode, ks, val_n=1000, out=None):
    ix = get_index()
    mode = resolve_mode(mode, ix)
    kmax = max(ks)
    t0 = time.time()

    # 1. test set (hors unanswerable)
    test = [t for t in C.read_jsonl(C.TEST) if t["category"] != "unanswerable"]
    ranks_by_cat, all_ranks, n_skip = defaultdict(list), [], 0
    misses = []
    for t in tqdm(test, desc="test", unit="q"):
        exp = expected_pages(t.get("source"))
        if not exp:
            n_skip += 1
            continue
        res = retrieve(t["question"], kmax, mode)
        r = _hit_rank(res, lambda p: (p["source"], p["title"].lower()) in exp)
        ranks_by_cat[t["category"]].append(r)
        all_ranks.append(r)
        if r is None:
            misses.append(t["id"])

    # 2. paires LLM du split val : chunk exact et page
    pairs = [p for p in C.read_jsonl(C.PAIRS) if p["kind"] == "llm" and p["split"] == "val"
             and p["chunk_id"] in ix.pos]
    random.Random(0).shuffle(pairs)
    pairs = pairs[:val_n]
    r_chunk, r_page = [], []
    for p in tqdm(pairs, desc="val", unit="q"):
        res = retrieve(p["question"], kmax, mode)
        r_chunk.append(_hit_rank(res, lambda d: d["id"] == p["chunk_id"]))
        r_page.append(_hit_rank(res, lambda d: d["source"] == p["source"] and d["title"] == p["title"]))

    def row(name, ranks):
        return f"| {name} | {len(ranks)} | " + " | ".join(f"{_pct(ranks, k):.1f}" for k in ks) + " |"

    head = "| ensemble | n | " + " | ".join(f"hit@{k}" for k in ks) + " |\n|---|---|" + "---|" * len(ks)
    lines = [f"# Qualite de la recherche (mode {mode}, {time.strftime('%Y-%m-%d')})", "",
             f"Index : {len(ix.docs)} documents (chunks + fiches de faits), embeddings : "
             f"{'oui' if ix.emb is not None else 'non'}. Valeurs en %. Max 2 passages par page.", "",
             "## Jeu de test (page attendue = champ `source`, hors unanswerable)", "", head,
             row("toutes categories", all_ranks)]
    for cat in sorted(ranks_by_cat):
        lines.append(row(cat, ranks_by_cat[cat]))
    lines += ["", f"{n_skip} questions sans source exploitable ignorees. Ratees a k={kmax} : {', '.join(misses) or '-'}", "",
              f"## Paires LLM du split val ({len(pairs)} tirees, graine 0)", "", head,
              row("chunk exact", r_chunk), row("page", r_page), "",
              f"Duree : {time.time() - t0:.0f} s"]
    text = "\n".join(lines) + "\n"
    print(text)
    path = C.Path(out) if out else (C.REPORT / ("retrieval.md" if mode == "bm25" else f"retrieval_{mode}.md"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"-> {path}")
