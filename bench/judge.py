"""ow-bench judge : LLM-juge par lots, contre la reponse de reference (reprenable)."""
import datetime as dt
import json
import signal

from tqdm import tqdm

from bench import common as C
from bench.backends import BackendError, RateLimitError, make_backend

BATCH = 15
ANSWERABLE = ("correct", "partial", "incorrect", "abstained")
UNANSWERABLE = ("correct", "hallucinated")

JUDGE_SYSTEM = """You are a strict but fair grader for a question-answering benchmark about the video game Overwatch.
For each item you get: the question, a REFERENCE answer (ground truth), an optional note, a flag "unanswerable", and the MODEL answer to grade.

Rules:
- The REFERENCE is the truth, even if it contradicts your own knowledge (many facts date from 2025-2026, after your training data). Never use your own knowledge to overrule it.
- Exact numbers, dates and names are required. Extra details are tolerated as long as they do not contradict the reference.
- Verdicts for normal items (unanswerable=false):
  "correct"   : the model answer matches the reference on all essential points;
  "partial"   : some essential points are right but others are missing or wrong (e.g. 1 of 2 facts requested);
  "incorrect" : the main fact is wrong or contradicts the reference;
  "abstained" : the model says it does not know / cannot answer, without giving the fact.
- For items with unanswerable=true (future events, invented entities, false premises) the reference describes the expected behaviour:
  "correct"      : the model declines to answer, says it does not know / cannot verify, or corrects the false premise;
  "hallucinated" : the model answers as if the premise were true and invents facts.
- Judge the content, not the style or length.

Output ONLY a JSON array, one object per item, in the same order: [{"id": "...", "verdict": "...", "reason": "<one short sentence>"}]. No markdown, no other text."""


_stop = {"flag": False}


def _on_sigint(signum, frame):
    if _stop["flag"]:
        raise KeyboardInterrupt
    _stop["flag"] = True
    tqdm.write("Ctrl+C : arret apres le lot en cours (Ctrl+C encore pour abandonner)")


def judge_config_from_spec(spec):
    backend, _, model = spec.partition(":")
    if not model:
        raise SystemExit("--judge attendu sous la forme backend:modele (ex. claude_cli:sonnet)")
    return {"name": f"judge-{spec}", "backend": backend, "model": model, "think": False,
            "temperature": 0, "max_tokens": 4096}


def parse_array(text):
    """Extrait le 1er tableau JSON de la reponse du juge (tolere texte autour / blocs markdown)."""
    dec = json.JSONDecoder()
    i = text.find("[")
    while i != -1:
        try:
            obj, _ = dec.raw_decode(text[i:])
            if isinstance(obj, list):
                return obj
        except ValueError:
            pass
        i = text.find("[", i + 1)
    raise ValueError("aucun tableau JSON dans la reponse du juge")


def _valid(item, q):
    allowed = UNANSWERABLE if q["category"] == "unanswerable" else ANSWERABLE
    return isinstance(item, dict) and item.get("verdict") in allowed


def _judge_batch(backend, items, qmap):
    """items : liste de (question, run_row). Retourne {id: {verdict, reason}} ; coupe le lot en deux si besoin."""
    payload = [{"id": q["id"], "question": q["question"], "reference": q["answer"], "note": q.get("note", ""),
                "unanswerable": q["category"] == "unanswerable", "model_answer": r["text"] or "(empty answer)"}
               for q, r in items]
    messages = [{"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}]
    last = ""
    for attempt in range(3):
        try:
            res = backend.answer(messages)
            arr = parse_array(res["text"])
            got = {a.get("id"): a for a in arr if isinstance(a, dict)}
            if all(q["id"] in got and _valid(got[q["id"]], q) for q, _ in items):
                return {q["id"]: {"verdict": got[q["id"]]["verdict"], "reason": got[q["id"]].get("reason", "")}
                        for q, _ in items}
            last = "verdicts manquants ou invalides"
        except RateLimitError:
            raise
        except (ValueError, BackendError) as e:
            last = str(e)
        tqdm.write(f"juge: essai {attempt + 1}/3 echoue ({last})")
    if len(items) == 1:
        tqdm.write(f"juge: abandon de {items[0][0]['id']} ({last})")
        return {}
    mid = len(items) // 2
    out = _judge_batch(backend, items[:mid], qmap)
    out.update(_judge_batch(backend, items[mid:], qmap))
    return out


def judge(names, spec="claude_cli:sonnet", runs_dir=C.RUNS, out_dir=C.JUDGMENTS, batch=BATCH):
    out_dir.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGINT, _on_sigint)
    jcfg = judge_config_from_spec(spec)
    backend = make_backend(jcfg)
    qmap = {q["id"]: q for q in C.load_test()}
    stop_file = runs_dir / "STOP"
    try:
        backend.prepare()
        for name in names:
            runs = C.latest_by_id(C.read_jsonl(runs_dir / f"{name}.jsonl"))
            jpath = out_dir / f"{name}.jsonl"
            done = {(j["id"], j["qhash"], j["run_ts"]) for j in C.read_jsonl(jpath) if j.get("judge") == spec}
            todo = [(qmap[i], r) for i, r in runs.items() if i in qmap and r["qhash"] == qmap[i]["qhash"]
                    and (i, r["qhash"], r["ts"]) not in done]
            print(f"[{name}] {len(runs)} reponses, {len(runs) - len(todo)} deja jugees, {len(todo)} a juger "
                  f"(juge {spec}) -> {jpath}")
            batches = [todo[i:i + batch] for i in range(0, len(todo), batch)]
            with open(jpath, "a", encoding="utf-8") as out:
                for b in tqdm(batches, unit="lot", desc=name):
                    if _stop["flag"] or stop_file.exists():
                        print("Arret demande.")
                        return
                    verdicts = _judge_batch(backend, b, qmap)
                    for q, r in b:
                        v = verdicts.get(q["id"])
                        if not v:
                            continue
                        out.write(json.dumps({"id": q["id"], "qhash": r["qhash"], "run_ts": r["ts"],
                                              "config": name, "judge": spec, **v,
                                              "ts": dt.datetime.now().isoformat(timespec="seconds")},
                                             ensure_ascii=False) + "\n")
                    out.flush()
    except RateLimitError as e:
        print(f"Limite d'abonnement atteinte ({e}) : relancer plus tard, la reprise saute les lots faits.")
    except KeyboardInterrupt:
        print("Interrompu.")
