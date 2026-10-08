"""ow-bench run : pose les questions du jeu de test a une configuration (reprenable)."""
import csv
import datetime as dt
import json
import random
import signal

from tqdm import tqdm

from bench import common as C
from bench.backends import BackendError, RateLimitError, make_backend
from bench.prompts import build_messages

_stop = {"flag": False}


def _on_sigint(signum, frame):
    if _stop["flag"]:
        raise KeyboardInterrupt
    _stop["flag"] = True
    tqdm.write("Ctrl+C : arret apres la question en cours (Ctrl+C encore pour abandonner)")


def select_questions(ids=None, category=None):
    qs = C.load_test()
    if ids:
        wanted = set(ids)
        qs = [q for q in qs if q["id"] in wanted]
    if category:
        qs = [q for q in qs if q["category"] == category]
    # ordre melange a graine fixe : un ralentissement GPU ne tombe pas sur une seule categorie
    random.Random(0).shuffle(qs)
    return qs


def done_keys(path):
    return {(r["id"], r["qhash"]) for r in C.read_jsonl(path)}


def _retrieve(question, k):
    try:
        from rag.retrieve import retrieve
    except ImportError:
        raise SystemExit("Index RAG absent : le module rag.retrieve (lot RAG) n'existe pas encore. "
                         "Il doit exposer retrieve(question, k) -> liste de dicts {'id', 'text'}.")
    return retrieve(question, k)


def run(names, limit=None, ids=None, category=None):
    C.RUNS.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGINT, _on_sigint)
    for name in names:
        if _stop["flag"] or C.STOP_FILE.exists():
            break
        cfg = C.get_config(name)
        out_path = C.RUNS / f"{name}.jsonl"
        qs = select_questions(ids, category)
        done = done_keys(out_path)
        todo = [q for q in qs if (q["id"], q["qhash"]) not in done]
        print(f"[{name}] {len(qs)} questions selectionnees, {len(qs) - len(todo)} deja faits, "
              f"{len(todo)} a faire -> {out_path}")
        if limit:
            todo = todo[:limit]
        if not todo:
            continue
        backend = make_backend(cfg)
        reason, n = "termine", 0
        bar = None
        try:
            backend.prepare()
            bar = tqdm(todo, unit="q", desc=name)
            with open(out_path, "a", encoding="utf-8") as out:
                for q in bar:
                    if _stop["flag"]:
                        reason = "ctrl-c"
                        break
                    if C.STOP_FILE.exists():
                        reason = "fichier STOP"
                        break
                    passages = None
                    if cfg.get("rag"):
                        passages = _retrieve(q["question"], cfg["rag"].get("k", 5))
                    try:
                        res = backend.answer(build_messages(q["question"], passages))
                    except RateLimitError as e:
                        reason = f"limite d'abonnement/quota ({e})"
                        break
                    except (BackendError, OSError, ValueError) as e:
                        tqdm.write(f"echec {q['id']}: {type(e).__name__}: {e}")
                        continue
                    row = {"id": q["id"], "qhash": q["qhash"], "config": name, "model": cfg["model"],
                           "text": res["text"], "latency_s": res["latency_s"], "ttft_s": res["ttft_s"],
                           "out_tokens": res["out_tokens"], "think_tokens": res["think_tokens"],
                           "in_tokens": res["in_tokens"], "tok_s": res["tok_s"], "vram_mb": res["vram_mb"],
                           "cost_usd": res["cost_usd"],
                           "rag_ids": [p["id"] for p in passages] if passages else None,
                           "ts": dt.datetime.now().isoformat(timespec="seconds")}
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
                    n += 1
        except BackendError as e:
            reason = f"erreur backend: {e}"
        except KeyboardInterrupt:
            reason = "ctrl-c (requete abandonnee)"
        finally:
            if bar:
                bar.close()
        print(f"[{name}] Arret: {reason}. Questions faites: {n}.")
        if reason.startswith("limite"):
            break


def export_questions(name, path=None):
    path = path or (C.EVAL / f"questions_{name}.csv")
    qs = select_questions()
    done = done_keys(C.RUNS / f"{name}.jsonl")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "question", "answer"])
        for q in qs:
            if (q["id"], q["qhash"]) not in done:
                w.writerow([q["id"], q["question"], ""])
    print(f"Questions ecrites dans {path} (remplir la colonne answer, puis import-answers)")


def import_answers(name, path):
    cfg = C.get_config(name)
    by_id = {q["id"]: q for q in C.load_test()}
    out_path = C.RUNS / f"{name}.jsonl"
    done = done_keys(out_path)
    n = 0
    C.RUNS.mkdir(parents=True, exist_ok=True)
    with open(path, encoding="utf-8-sig", newline="") as f, open(out_path, "a", encoding="utf-8") as out:
        for r in csv.DictReader(f, delimiter=";"):
            q = by_id.get(r["id"])
            if not q or not (r.get("answer") or "").strip() or (q["id"], q["qhash"]) in done:
                continue
            row = {"id": q["id"], "qhash": q["qhash"], "config": name, "model": cfg["model"],
                   "text": r["answer"].strip(), "latency_s": None, "ttft_s": None, "out_tokens": None,
                   "think_tokens": None, "in_tokens": None, "tok_s": None, "vram_mb": None, "cost_usd": 0.0,
                   "rag_ids": None, "ts": dt.datetime.now().isoformat(timespec="seconds")}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} reponses importees dans {out_path}")
