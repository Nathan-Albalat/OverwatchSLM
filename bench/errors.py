"""Provenance des erreurs des bras + RAG : la reponse de reference etait-elle dans les passages recus ?
- non     -> erreur de RECHERCHE (le modele ne pouvait pas trouver la reponse dans son contexte) ;
- oui     -> erreur de LECTURE (la reponse etait la, le modele ne l'a pas exploitee) ;
- partiel -> une partie seulement de la reponse etait dans les passages.
Verification par le LLM local (qwen3.6, meme prompt que la verification des refus RAFT), en cache par
(question, passages) : les bras qui ont recu les memes passages ne sont verifies qu'une fois.
Sorties : eval/report/error_sources.jsonl (cache) et eval/report/error_sources.md.

Usage : python -m bench.errors [config...]   (defaut : toutes les configs + RAG jugees)
"""
import hashlib
import json
import sys

from tqdm import tqdm

from bench import common as C
from bench.prompts import format_user_prompt
from rag.augment import SEP, VERIFY_PROMPT, ask_json

OUT = C.ROOT / "eval" / "report" / "error_sources.jsonl"
MD = C.ROOT / "eval" / "report" / "error_sources.md"
LABEL = {"no": "recherche", "partial": "partiel", "yes": "lecture"}


def _key(qid, ids):
    return qid + "|" + hashlib.sha1("|".join(ids).encode()).hexdigest()[:12]


def _docs(ids):
    want, out = set(ids), {}
    with open(C.ROOT / "data" / "rag" / "docs.jsonl", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["id"] in want:
                out[d["id"]] = d
    return out


def main(names=None):
    test = {q["id"]: q for q in C.load_test()}
    rag_cfgs = [n for n, c in C.load_configs().items() if c.get("rag")]
    names = names or [n for n in rag_cfgs if (C.JUDGMENTS / f"{n}.jsonl").exists()]
    errors = {}   # config -> [(qid, verdict, key)]
    todo = {}     # key -> (qid, ids)
    for n in names:
        runs = {r["id"]: r for r in C.read_jsonl(C.RUNS / f"{n}.jsonl")}
        errors[n] = []
        for j in C.read_jsonl(C.JUDGMENTS / f"{n}.jsonl"):
            q = test.get(j["id"])
            if not q or q["category"] == "unanswerable" or j["verdict"] == "correct":
                continue
            ids = runs[j["id"]].get("rag_ids") or []
            k = _key(j["id"], ids)
            errors[n].append((j["id"], j["verdict"], k))
            todo[k] = (j["id"], ids)
    cache = {r["key"]: r for r in C.read_jsonl(OUT)}
    missing = {k: v for k, v in todo.items() if k not in cache}
    print(f"[errors] {len(names)} configs, {sum(map(len, errors.values()))} erreurs, "
          f"{len(todo)} couples (question, passages) distincts, {len(missing)} a verifier")
    if missing:
        docs = _docs({i for _, ids in missing.values() for i in ids})
        with open(OUT, "a", encoding="utf-8") as f:
            for k, (qid, ids) in tqdm(missing.items(), desc="verify"):
                q = test[qid]
                passages = [{"id": i, "text": docs[i]["text"]} for i in ids if i in docs]
                ctx = format_user_prompt(q["question"], passages).rsplit(SEP, 1)[0]
                try:
                    v = ask_json(VERIFY_PROMPT.format(ctx=ctx, q=q["question"], a=q["answer"]), num_predict=500)
                    verdict = str(v.get("verdict", "")).lower()
                    if verdict not in LABEL:
                        raise ValueError(verdict)
                except (ValueError, KeyError) as e:
                    tqdm.write(f"  erreur {qid}: {e}")
                    continue
                rec = {"key": k, "id": qid, "verdict": verdict, "passage": v.get("passage"),
                       "why": str(v.get("why", ""))[:300]}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                cache[k] = rec
    rows = []
    for n in names:
        c = {"recherche": 0, "partiel": 0, "lecture": 0, "?": 0}
        for _, _, k in errors[n]:
            c[LABEL.get(cache.get(k, {}).get("verdict"), "?")] += 1
        tot = sum(c.values()) or 1
        rows.append(f"| {n} | {sum(c.values())} | {c['recherche']} ({100 * c['recherche'] / tot:.0f} %) | "
                    f"{c['partiel']} ({100 * c['partiel'] / tot:.0f} %) | {c['lecture']} ({100 * c['lecture'] / tot:.0f} %) |"
                    + (f" {c['?']} non verifiees |" if c["?"] else " |"))
    md = ["# Provenance des erreurs des bras + RAG", "",
          "Erreurs = questions repondables non jugees `correct` (partielles, incorrectes, abstentions). "
          "Pour chacune, `qwen3.6:35b-a3b` verifie si les passages recus contenaient la reponse de reference "
          "(`bench/errors.py`, prompt de verification des refus RAFT). Verification automatique, indicative.", "",
          "| config | erreurs | recherche (reponse absente des passages) | partiel | lecture (reponse presente) | |",
          "|---|---|---|---|---|---|", *rows, ""]
    MD.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main(sys.argv[1:] or None)
