"""ow-rag augment / devset : corrections des exemples RAFT par LLM local (qwen3.6, GPU) et jeu de developpement.

Diagnostic du RAFT v1 (Qwen3-4B, 13 oct.) : sur raft_val il ne refuse que 3 % des exemples oracle, mais sur le test il
s'abstient 2,5 fois plus que le 4B de base. Cause principale : les questions d'entrainement sont generees a partir du
passage oracle et en reprennent les mots, alors que les questions du test sont ecrites independamment ; cause secondaire :
~12 % des refus sont faux (reponse presente sous une autre forme que celle detectee par `answer_in`).

Etapes (toutes reprenables : append JSONL par id, arret propre par data/rag/STOP ou Ctrl+C) :
  paraphrase  reformule la question d'une part des exemples oracle / answer_in_distractor   -> <dir>/paraphrases.jsonl
  verify      le LLM dit si les passages d'un exemple « refus » contiennent quand meme la reponse -> <dir>/verify.jsonl
  apply       ecrit <dir>/raft_{train,val}_final.jsonl (questions reformulees, faux refus retires) + augment_stats.json
  devset      eval/dev_set.jsonl : questions de paires val (pages jamais vues a l'entrainement) reformulees + questions
              sans reponse inventees ; sert a regler les variantes RAFT sans toucher au jeu de test.
"""
import hashlib
import json
import random
import signal
from collections import Counter
from pathlib import Path

import requests
from tqdm import tqdm

from rag import common as C

GEN_MODEL = "qwen3.6:35b-a3b"
DEV_SET = C.ROOT / "eval" / "dev_set.jsonl"
SEP = "\n\nQuestion: "            # bench.prompts.format_user_prompt : passages puis « Question: ... »
_stop = {"flag": False}

PARAPHRASE_PROMPT = """Rewrite this question about the video game Overwatch the way a different player would naturally ask it.
- Change the wording and the sentence structure; prefer everyday player vocabulary over the wiki's phrasing.
- Do not reuse distinctive phrases of the original question unless they are names.
- Keep every named entity (hero, ability, map, team, player, tournament, patch date, season) so the question stays
  unambiguous and has exactly the same answer.
- Do not add information, do not answer it.

Question: {q}
(Its answer, for your reference only: {a})

Reply with JSON only: {{"question": "<rewritten question>"}}"""

VERIFY_PROMPT = """You check a question-answering dataset. Below are numbered passages, a question, and the reference answer.
Decide whether the passages contain enough information to give the reference answer to THIS question
(the same entity, event, date or version as asked: information about a different tournament, patch or hero does not count).

{ctx}

Question: {q}
Reference answer: {a}

Reply with JSON only: {{"verdict": "yes" | "partial" | "no", "passage": <number or null>, "why": "<short reason>"}}"""

UNANSWERABLE_PROMPT = """You help build an evaluation set about the video game Overwatch. Here is a real question for inspiration:
{q}

Write ONE new question in a similar style that cannot be answered from any Overwatch source, using this trick: {trick}.
Make it sound plausible. Reply with JSON only:
{{"question": "<question>", "answer": "<what a good answer should say, e.g. 'X does not exist in Overwatch; the model should say it does not know or correct the premise.'>"}}"""

TRICKS = ["it asks about an invented hero, map or ability presented as real",
          "it asks about a future event (2027 or later) as if it had already happened",
          "it relies on a false premise about a real hero or tournament (something that never happened)",
          "it asks about an invented esports player or team presented as real"]

# categories des paires -> categories du banc (eval/report)
CAT_MAP = {"hero": "gameplay", "ability": "gameplay", "ability_stats": "gameplay", "hero_stats": "gameplay",
           "tournament": "esport", "team": "esport", "player": "esport", "award": "esport",
           "patch": "patch", "map": "maps_modes", "event": "maps_modes", "story": "lore", "other": "lore"}


def _on_sigint(signum, frame):
    if _stop["flag"]:
        raise KeyboardInterrupt
    _stop["flag"] = True
    tqdm.write("Ctrl+C : arret apres l'element en cours (Ctrl+C encore pour abandonner)")


def _stopped():
    return _stop["flag"] or C.STOP_FILE.exists()


def ask_json(prompt, model=GEN_MODEL, temperature=0.0, num_predict=300):
    body = {"model": model, "stream": False, "think": False, "format": "json", "keep_alive": "30m",
            "options": {"temperature": temperature, "num_ctx": 8192, "num_predict": num_predict},
            "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(f"{C.OLLAMA}/api/chat", json=body, timeout=600)
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def _frac(key, seed=0):
    """Tirage deterministe dans [0, 1) par id (meme selection d'une relance a l'autre)."""
    return int(hashlib.sha1(f"{seed}|{key}".encode()).hexdigest()[:8], 16) / 2**32


def split_user(content):
    ctx, q = content.rsplit(SEP, 1)
    return ctx, q


def _loop(items, out_path, fn, desc):
    """Applique fn(item) -> dict et ecrit {"id", ...} en append ; saute les ids deja faits."""
    done = {r["id"] for r in C.read_jsonl(out_path)}
    todo = [it for it in items if it["id"] not in done]
    print(f"[{desc}] {len(items)} selectionnes, {len(done)} deja faits, {len(todo)} a faire -> {out_path}")
    signal.signal(signal.SIGINT, _on_sigint)
    reason, n, errors = "termine", 0, 0
    bar = tqdm(todo, unit="ex", desc=desc)
    try:
        with open(out_path, "a", encoding="utf-8") as out:
            for it in bar:
                if _stopped():
                    reason = "arret demande (STOP ou Ctrl+C)"
                    break
                try:
                    res = fn(it)
                except (requests.RequestException, ValueError, KeyError) as e:
                    errors += 1
                    tqdm.write(f"  erreur {it['id']}: {type(e).__name__}: {e}"[:200])
                    continue
                out.write(json.dumps({"id": it["id"], **res}, ensure_ascii=False) + "\n")
                out.flush()
                n += 1
    except KeyboardInterrupt:
        reason = "ctrl-c (abandon)"
    finally:
        bar.close()
    print(f"Arret: {reason}. {n} ecrits, {errors} erreurs (relancer pour reprendre).")
    return reason == "termine"


def _examples(d):
    out = []
    for split in ("train", "val"):
        for e in C.read_jsonl(d / f"raft_{split}.jsonl"):
            e["split"] = split
            out.append(e)
    return out


def paraphrase(d, share=0.5, seed=0):
    d = Path(d)
    items = [e for e in _examples(d) if e["type"] != "refusal" and _frac(e["id"], seed) < share]

    def fn(e):
        _, q = split_user(e["messages"][-2]["content"])
        nq = str(ask_json(PARAPHRASE_PROMPT.format(q=q, a=e["messages"][-1]["content"]), temperature=0.7)
                 .get("question", "")).strip()
        if len(nq) < 8:
            raise ValueError("reformulation vide")
        return {"question": nq, "original": q}
    return _loop(items, d / "paraphrases.jsonl", fn, "paraphrase")


def verify(d):
    d = Path(d)
    answers = {p["id"]: p["answer"] for p in C.read_jsonl(C.PAIRS)}
    items = [e for e in _examples(d) if e["type"] == "refusal"]
    missing = [e["id"] for e in items if e["id"] not in answers]
    if missing:
        raise SystemExit(f"{len(missing)} exemples sans paire dans {C.PAIRS} (dataset reconstruit depuis ?) ex. {missing[:3]}")

    def fn(e):
        ctx, q = split_user(e["messages"][-2]["content"])
        v = ask_json(VERIFY_PROMPT.format(ctx=ctx, q=q, a=answers[e["id"]]))
        verdict = str(v.get("verdict", "")).lower()
        if verdict not in ("yes", "partial", "no"):
            raise ValueError(f"verdict invalide: {verdict!r}")
        return {"verdict": verdict, "passage": v.get("passage"), "why": str(v.get("why", ""))[:300]}
    return _loop(items, d / "verify.jsonl", fn, "verify")


def apply(d, drop=("yes", "partial")):
    d = Path(d)
    para = {r["id"]: r["question"] for r in C.read_jsonl(d / "paraphrases.jsonl")}
    ver = {r["id"]: r["verdict"] for r in C.read_jsonl(d / "verify.jsonl")}
    stats = {"drop_verdicts": list(drop)}
    for split in ("train", "val"):
        rows = C.read_jsonl(d / f"raft_{split}.jsonl")
        refusals = [e for e in rows if e["type"] == "refusal"]
        unverified = sum(e["id"] not in ver for e in refusals)
        if unverified:
            print(f"ATTENTION [{split}] {unverified} refus non verifies (gardes tels quels) : relancer `augment verify`")
        st = Counter(n_in=len(rows), unverified_refusals=unverified)
        with open(d / f"raft_{split}_final.jsonl", "w", encoding="utf-8") as out:
            for e in rows:
                if e["type"] == "refusal" and ver.get(e["id"]) in drop:
                    st[f"dropped_refusal_{ver[e['id']]}"] += 1
                    continue
                if e["id"] in para:
                    ctx, _ = split_user(e["messages"][-2]["content"])
                    e["messages"][-2]["content"] = ctx + SEP + para[e["id"]]
                    e["paraphrased"] = True
                    st["paraphrased"] += 1
                st[e["type"]] += 1
                st["n_out"] += 1
                out.write(json.dumps(e, ensure_ascii=False) + "\n")
        stats[split] = dict(st)
    (d / "augment_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


def devset(n=300, n_unanswerable=30, seed=0, template_share=0.1):
    """Paires du split val (pages absentes de l'entrainement, presentes dans l'index RAG comme pour le test)."""
    rng = random.Random(seed)
    pairs = [p for p in C.read_jsonl(C.PAIRS) if p["split"] == "val"]
    n_tpl = round(n * template_share)
    by_kind = {k: [p for p in pairs if p["kind"] == k] for k in ("llm", "template")}
    sel = []
    for kind, m in (("llm", n - n_tpl), ("template", n_tpl)):
        # au plus 2 questions par page : evite qu'une grosse page de tournoi domine
        pool, per_page = by_kind[kind], Counter()
        rng.shuffle(pool)
        for p in pool:
            if len(sel) >= (n - n_tpl if kind == "llm" else n) or per_page[p["title"]] >= 2:
                continue
            per_page[p["title"]] += 1
            sel.append(p)
    raw = DEV_SET.with_suffix(".raw.jsonl")
    items = [{"id": f"D{i + 1:03d}", "pair": p} for i, p in enumerate(sel)]
    inspire = rng.sample(sel, n_unanswerable)
    items += [{"id": f"DU{i + 1:02d}", "inspire": p["question"], "trick": TRICKS[i % len(TRICKS)]}
              for i, p in enumerate(inspire)]

    def fn(it):
        if "pair" in it:
            p = it["pair"]
            nq = str(ask_json(PARAPHRASE_PROMPT.format(q=p["question"], a=p["answer"]), temperature=0.7)
                     .get("question", "")).strip()
            if len(nq) < 8:
                raise ValueError("reformulation vide")
            return {"category": CAT_MAP.get(p.get("category"), "lore"), "temporal": False, "question": nq,
                    "answer": p["answer"], "source": f"{p['source']}:{p['title']}",
                    "note": f"dev : paire val {p['id']} reformulee (question d'origine : {p['question']})"}
        v = ask_json(UNANSWERABLE_PROMPT.format(q=it["inspire"], trick=it["trick"]), temperature=0.9)
        q, a = str(v.get("question", "")).strip(), str(v.get("answer", "")).strip()
        if len(q) < 8 or len(a) < 8:
            raise ValueError("question sans reponse vide")
        return {"category": "unanswerable", "temporal": False, "question": q, "answer": a, "source": "",
                "note": f"dev : genere ({it['trick']})"}
    if not _loop(items, raw, fn, "devset"):
        return
    rows = {r["id"]: r for r in C.read_jsonl(raw)}
    with open(DEV_SET, "w", encoding="utf-8") as out:
        for it in items:
            if it["id"] in rows:
                out.write(json.dumps(rows[it["id"]], ensure_ascii=False) + "\n")
    cats = Counter(r["category"] for r in rows.values())
    print(f"{len(rows)} questions -> {DEV_SET} {dict(cats)}")
