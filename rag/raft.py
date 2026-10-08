"""ow-rag raft : exemples d'entrainement RAFT (question + passages dont distracteurs -> reponse ou refus).

Part des paires finales (data/dataset/pairs.jsonl, deja filtrees et nettoyees du test). Les distracteurs sont
les resultats du vrai retriever (memes conditions qu'a l'inference). Reprenable : append + skip des ids faits ;
le tirage de chaque exemple depend uniquement de (graine, id), donc d'une relance a l'autre le resultat est identique.
"""
import json
import random
import signal
from collections import defaultdict
from pathlib import Path

from tqdm import tqdm

from bench.prompts import build_messages
from gen.build_dataset import _keys, _numbers
from rag import common as C
from rag.retrieve import get_index, resolve_mode, retrieve

REFUSALS = [
    "The provided passages do not contain this information, so I cannot answer reliably.",
    "I cannot find this information in the provided passages, so I do not know.",
    "None of the passages answer this question, so I cannot give a reliable answer.",
    "The passages do not mention this, and I do not want to guess: I do not know.",
]
VAL_SHARE = 0.05
_stop = {"flag": False}


def _on_sigint(signum, frame):
    if _stop["flag"]:
        raise KeyboardInterrupt
    _stop["flag"] = True
    tqdm.write("Ctrl+C : arret apres l'exemple en cours (Ctrl+C encore pour abandonner)")


def trunc(text, n):
    w = text.split(" ")
    return text if len(w) <= n else " ".join(w[:n]) + " ..."


def answer_in(answer, text):
    """Les elements cles de la reponse (tous les nombres, >= 80 % des entites) figurent-ils dans le texte ?"""
    nums = _numbers(answer)
    ents = _keys(answer) - nums
    if not nums and not ents:
        return False
    low = text.lower()
    if nums and not nums <= _numbers(text):
        return False
    return not ents or sum(e in low for e in ents) / len(ents) >= 0.8


def stratified(pairs, n, rng):
    """n paires, quotas proportionnels par (source, categorie), ordre melange (graine fixe)."""
    groups = defaultdict(list)
    for p in pairs:
        groups[(p["source"], p.get("category"))].append(p)
    for key in sorted(groups, key=str):
        rng.shuffle(groups[key])
    if n >= len(pairs):
        out = list(pairs)
    else:
        out, total = [], len(pairs)
        for key in sorted(groups, key=str):
            g = groups[key]
            out += g[:max(1, round(n * len(g) / total))]
        rng.shuffle(out)
        out = out[:n]
    rng.shuffle(out)
    return out


def select(ix, tmap, n, template_share, seed):
    pairs = C.read_jsonl(C.PAIRS)
    rng = random.Random(seed)
    cand = {"train": {"llm": [], "template": []}, "val": {"llm": [], "template": []}}
    for p in pairs:
        if p["kind"] == "template":
            oid = tmap.get(p["id"], p["chunk_id"])   # fiche de faits si le fait n'est pas dans le texte du chunk
        else:
            oid = p["chunk_id"]
        if oid not in ix.pos:
            continue
        p["oracle_id"] = oid
        cand[p["split"]][p["kind"]].append(p)
    n_val = round(n * VAL_SHARE)
    out = {}
    for split, total in (("train", n - n_val), ("val", n_val)):
        n_tpl = round(total * template_share)
        sel = stratified(cand[split]["llm"], total - n_tpl, rng) + stratified(cand[split]["template"], n_tpl, rng)
        rng.shuffle(sel)
        out[split] = sel
    return out


def make_example(p, ix, k, p_oracle, mode, seed, max_words):
    rng = random.Random(f"{seed}|{p['id']}")
    oracle = ix.docs[ix.pos[p["oracle_id"]]]
    with_oracle = rng.random() < p_oracle
    if with_oracle:
        dis = retrieve(p["question"], k - 1, mode, exclude_ids=[oracle["id"]])
        otext = trunc(oracle["text"], max_words)
        if not answer_in(p["answer"], otext):          # reponse hors de la fenetre : on elargit
            otext = trunc(oracle["text"], 2 * max_words)
        passages = [{"id": d["id"], "text": trunc(d["text"], max_words)} for d in dis]
        passages.insert(rng.randrange(len(passages) + 1), {"id": oracle["id"], "text": otext})
        target, kind = p["answer"], "oracle"
    else:
        dis = retrieve(p["question"], k, mode, exclude_ids=[oracle["id"]])
        passages = [{"id": d["id"], "text": trunc(d["text"], max_words)} for d in dis]
        if any(answer_in(p["answer"], d["text"]) for d in passages):
            target, kind = p["answer"], "refusal_cancelled"
        else:
            target, kind = rng.choice(REFUSALS), "refusal"
    msgs = build_messages(p["question"], passages) + [{"role": "assistant", "content": target}]
    return {"id": p["id"], "kind": p["kind"], "type": kind, "oracle_id": oracle["id"],
            "passage_ids": [d["id"] for d in passages], "messages": msgs}


def _tokens(ex):
    return sum(len(m["content"].split()) for m in ex["messages"]) * 1.35


def compute_stats(out_dir):
    st = {}
    for split in ("train", "val"):
        rows = C.read_jsonl(out_dir / f"raft_{split}.jsonl")
        cnt = {t: sum(r["type"] == t for r in rows) for t in ("oracle", "refusal", "refusal_cancelled")}
        toks = [_tokens(r) for r in rows]
        st[split] = {"n": len(rows), **cnt,
                     "by_kind": {kd: sum(r["kind"] == kd for r in rows) for kd in ("llm", "template")},
                     "avg_tokens_est": round(sum(toks) / len(toks)) if toks else 0,
                     "max_tokens_est": round(max(toks)) if toks else 0,
                     "total_tokens_est": round(sum(toks))}
    return st


def run(n=15000, k=4, p_oracle=0.8, mode=None, seed=0, out_dir=None, template_share=0.1, max_words=400):
    ix = get_index()
    mode = resolve_mode(mode, ix)
    out_dir = Path(out_dir) if out_dir else C.ROOT / "data" / "dataset"
    out_dir.mkdir(parents=True, exist_ok=True)
    _, tmap = C.build_fact_cards(C.read_jsonl(C.TEMPLATES))
    sel = select(ix, tmap, n, template_share, seed)
    signal.signal(signal.SIGINT, _on_sigint)
    reason, n_done = "termine", 0
    for split in ("train", "val"):
        path = out_dir / f"raft_{split}.jsonl"
        done = {r["id"] for r in C.read_jsonl(path)}
        todo = [p for p in sel[split] if p["id"] not in done]
        print(f"[{split}] {len(sel[split])} selectionnes, {len(done)} deja faits, {len(todo)} a faire "
              f"(mode {mode}) -> {path}")
        bar = tqdm(todo, unit="ex", desc=split)
        try:
            with open(path, "a", encoding="utf-8") as out:
                for p in bar:
                    if _stop["flag"]:
                        reason = "ctrl-c"
                        break
                    if C.STOP_FILE.exists():
                        reason = "fichier STOP"
                        break
                    ex = make_example(p, ix, k, p_oracle, mode, seed, max_words)
                    out.write(json.dumps(ex, ensure_ascii=False) + "\n")
                    out.flush()
                    n_done += 1
        except KeyboardInterrupt:
            reason = "ctrl-c (abandon)"
        finally:
            bar.close()
        if reason != "termine":
            break
    st = {"params": {"n": n, "k": k, "p_oracle": p_oracle, "mode": mode, "seed": seed,
                     "template_share": template_share, "max_words": max_words}, **compute_stats(out_dir)}
    (out_dir / "raft_stats.json").write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Arret: {reason}. {n_done} exemples ecrits. Stats -> {out_dir / 'raft_stats.json'}")
    print(json.dumps({s: st[s] for s in ("train", "val")}, ensure_ascii=False))
