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
import re
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


def _examples(d, suffix=""):
    d = Path(d)
    out = []
    for split in ("train", "val"):
        for e in C.read_jsonl(d / f"raft_{split}{suffix}.jsonl"):
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
        rows = C.read_jsonl(d / f"raft_{split}{suffix}.jsonl")
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


# ---------------------------------------------------------------- RAFT v3 : questions composees et questions « joueur »
# Diagnostic du RAFT v2 : reponses trop courtes (14,5 mots contre 25 pour le 4B de base), un seul fait sur les questions
# composees, abstention sur les questions combinees, questions tapees vite (mots-cles, fautes) mal comprises.
#   compose   LLM : deuxieme paire du meme chunk -> question composee + reponse complete   -> <dir>/compose.jsonl
#   noisy     deterministe : apercu des questions reecrites en style « joueur » (mots-cles, minuscules, faute eventuelle)
#   apply3    <src>/raft_{train,val}_final.jsonl + compose + noisy -> <dir>/raft_{train,val}_final.jsonl + augment_stats.json
COMPOSE_PROMPT = """You build a question-answering dataset about the video game Overwatch. Two facts come from the same wiki passage.

Fact 1 - question: {q1}
Fact 1 - answer: {a1}

Fact 2 - question: {q2}
Fact 2 - answer: {a2}

Write:
- ONE natural compound question, the way a player would ask it in one sentence, that asks for both facts
  (for example "X, and Y?" or "What is X and what about Y?"). Name the subject explicitly (hero, team, tournament, patch...).
  Do not copy the wording of the two questions word for word.
- ONE complete answer in one to three sentences that gives BOTH facts, names the subject, and uses only the information above.

Reply with JSON only: {{"question": "<compound question>", "answer": "<complete answer>"}}"""

_RE_KEY = re.compile(r"\d+(?:[.,]\d+)*|[A-Z][\w'-]+")
_RE_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def _norm(s):
    return " ".join(re.findall(r"\w+", s.lower()))


def _jaccard(a, b):
    a, b = set(_norm(a).split()), set(_norm(b).split())
    return len(a & b) / max(1, len(a | b))


def _distractor_texts(e):
    """Textes des passages non oracle d'un exemple (decoupage sur « [i] » du prompt RAFT, aligne sur passage_ids)."""
    ctx, _ = split_user(e["messages"][-2]["content"])
    parts = re.split(r"\n\n\[(\d+)\] ", "\n\n" + ctx.split("\n\n", 1)[1])
    texts = [parts[i + 1] for i in range(1, len(parts) - 1, 2)]
    return [t for t, pid in zip(texts, e.get("passage_ids", [])) if pid != e.get("oracle_id")]


def _answer_leaks(answer, distractors):
    """Vrai si la reponse apparait mot pour mot dans un distracteur, ou si tous ses elements cles (>= 2 : nombres,
    noms propres) y figurent."""
    na = _norm(answer)
    keys = {k.lower() for k in _RE_KEY.findall(answer)}
    for t in distractors:
        nt = _norm(t)
        if na and na in nt:
            return True
        if len(keys) >= 2 and all(_norm(k) in nt for k in keys):
            return True
    return False


def _compose_items(src, share, seed, limit=None):
    pairs = list(C.read_jsonl(C.PAIRS))
    by_id = {p["id"]: p for p in pairs}
    by_chunk = {}
    for p in pairs:
        by_chunk.setdefault(p["chunk_id"], []).append(p)
    items, st = [], Counter()
    for e in _examples(src, "_final"):
        if e["type"] != "oracle" or _frac("compose|" + e["id"], seed) >= share:
            continue
        p1 = by_id.get(e["id"])
        if p1 is None:
            st["sans_paire"] += 1
            continue
        a1 = e["messages"][-1]["content"]
        cands = [p for p in by_chunk.get(e["oracle_id"], []) if p["id"] != p1["id"] and p["split"] == p1["split"]
                 and _jaccard(p["answer"], a1) < 0.5 and _jaccard(p["answer"], p1["answer"]) < 0.5
                 and _jaccard(p["question"], p1["question"]) < 0.8]
        if not cands:
            st["sans_partenaire"] += 1
            continue
        dist = _distractor_texts(e)
        cands.sort(key=lambda p: (_jaccard(p["answer"], a1), p["id"]))
        part = next((p for p in cands if not _answer_leaks(p["answer"], dist)), None)
        if part is None:
            st["partenaire_dans_distracteur"] += 1
            continue
        _, q1 = split_user(e["messages"][-2]["content"])
        items.append({"id": e["id"], "q1": q1, "a1": a1, "partner": part})
        st["ok"] += 1
    print(f"[compose] selection: {dict(st)}")
    return items[:limit] if limit else items


def compose(dst, src, share=0.3, seed=0, limit=None):
    dst, src = Path(dst), Path(src)
    dst.mkdir(parents=True, exist_ok=True)
    items = _compose_items(src, share, seed, limit)

    def fn(it):
        p = it["partner"]
        v = ask_json(COMPOSE_PROMPT.format(q1=it["q1"], a1=it["a1"], q2=p["question"], a2=p["answer"]),
                     temperature=0.3, num_predict=500)
        q, a = str(v.get("question", "")).strip(), str(v.get("answer", "")).strip()
        if len(q) < 15 or len(a.split()) < 8:
            raise ValueError("question ou reponse composee trop courte")
        return {"partner_id": p["id"], "question": q, "answer": a}
    return _loop(items, dst / "compose.jsonl", fn, "compose")


_NOISE_DROP = set("what which who whom whose when where why is are was were do does did the a an can could would will "
                  "has have had be been tell me please".split())


def noisy_question(q, key, seed=0):
    """Variante « joueur » deterministe (par key) ; renvoie q inchange si le resultat perdrait des entites ou nombres."""
    rng = random.Random(f"{seed}|{key}")
    toks = q.split()
    if rng.random() < 0.7:       # style mots-cles : on retire interrogatifs, auxiliaires, articles
        kept = [t for t in toks if re.sub(r"\W", "", t.lower()) not in _NOISE_DROP or re.search(r"\d", t)]
    else:                        # simple minuscules / ponctuation
        kept = toks[:]
    if len(kept) < 2:
        return q
    out = " ".join(kept)
    out = re.sub(r"[?!,;:]", "", out) if rng.random() < 0.5 else out.rstrip("?")
    if rng.random() < 0.85:
        out = out.lower()
    ents = {w.lower() for w in re.findall(r"[A-Z][\w'-]+", q)}
    if rng.random() < 0.15:      # une faute de frappe, sur un mot alphabetique >= 5 lettres qui n'est pas une entite
        ws = out.split()
        cand = [i for i, w in enumerate(ws) if len(w) >= 5 and w.isalpha() and w.lower() not in ents]
        if cand:
            i = rng.choice(cand)
            w, j = ws[i], rng.randrange(1, len(ws[i]) - 2)
            ws[i] = (w[:j] + w[j + 1] + w[j] + w[j + 2:]) if rng.random() < 0.5 else (w[:j] + w[j + 1:])
            out = " ".join(ws)
    low = out.lower()
    if any(n not in low for n in _RE_NUM.findall(q)):
        return q
    if any(re.sub(r"'s$", "", w.lower()) not in low for w in re.findall(r"[A-Z][\w'-]+", q)[1:]):
        return q
    return out


def _noisy_selected(e, share, seed):
    return e["type"] != "refusal" and _frac("noisy|" + e["id"], seed) < share


def noisy(src, limit=10, share=0.15, seed=0):
    """Apercu de n variantes bruitees (le calcul reel se fait dans apply3)."""
    n = 0
    for e in _examples(src, "_final"):
        if not _noisy_selected(e, share, seed):
            continue
        _, q = split_user(e["messages"][-2]["content"])
        nq = noisy_question(q, e["id"], seed)
        if nq != q:
            print(f"  {q}\n    -> {nq}")
            n += 1
            if n >= (limit or 10):
                break


def apply3(dst, src, share_noisy=0.15, seed=0):
    dst, src = Path(dst), Path(src)
    comp = {r["id"]: r for r in C.read_jsonl(dst / "compose.jsonl")}
    stats = {"src": str(src), "share_noisy": share_noisy, "seed": seed}
    wc = lambda e: len(e["messages"][-1]["content"].split())
    for split in ("train", "val"):
        rows = C.read_jsonl(src / f"raft_{split}_final.jsonl")
        st, before, after = Counter(n_in=len(rows)), [], []
        with open(dst / f"raft_{split}_final.jsonl", "w", encoding="utf-8") as out:
            for e in rows:
                before.append(wc(e))
                ctx, q = split_user(e["messages"][-2]["content"])
                if e["type"] == "oracle" and e["id"] in comp:
                    c = comp[e["id"]]
                    e["messages"][-2]["content"] = ctx + SEP + c["question"]
                    e["messages"][-1]["content"] = c["answer"]
                    e["composed"], e["partner_id"] = True, c["partner_id"]
                    st["composed"] += 1
                elif _noisy_selected(e, share_noisy, seed):
                    nq = noisy_question(q, e["id"], seed)
                    if nq != q:
                        e["messages"][-2]["content"] = ctx + SEP + nq
                        e["noisy"] = True
                        st["noisy"] += 1
                st[e["type"]] += 1
                st["n_out"] += 1
                after.append(wc(e))
                out.write(json.dumps(e, ensure_ascii=False) + "\n")
        st = dict(st)
        st["mean_answer_words_before"] = round(sum(before) / max(1, len(before)), 2)
        st["mean_answer_words_after"] = round(sum(after) / max(1, len(after)), 2)
        stats[split] = st
    (dst / "augment_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))
