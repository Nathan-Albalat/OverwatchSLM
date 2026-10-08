import datetime as dt
import json
import signal
import subprocess
import time
from pathlib import Path

import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "data" / "chunks" / "chunks.jsonl"
QA_DIR = ROOT / "data" / "qa"
OLLAMA = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.6:35b-a3b"

SCHEMA = {
    "type": "object",
    "properties": {"pairs": {"type": "array", "items": {
        "type": "object",
        "properties": {"question": {"type": "string"}, "answer": {"type": "string"}},
        "required": ["question", "answer"]}}},
    "required": ["pairs"],
}

SYSTEM = """You write question-answer training pairs about the video game Overwatch, from one passage of a wiki (Overwatch Fandom wiki or Liquipedia esports wiki).

Write 5 to 8 pairs (never more than 8; fewer only if the passage has very little content). Rules:
1. Use ONLY facts stated in the passage. Never add outside knowledge, never guess. Do not ask about anything the passage does not state.
2. Every question must be fully self-contained and understandable with no access to the passage. Always name the subject explicitly (the hero, ability, map, player, team, tournament, patch, event...). Never write "this page", "the passage", "the text", "the article", "he/she/they/it" without a name, or "this hero", "according to the description/passage/text". For story/lore passages, place the scene in context in the question (the character, story or event name given in "Page:" / "Section:"), e.g. "In the Soldier: 76 story, where was the joint CAF-Overwatch team deployed during the Omnic Crisis in Ottawa?".
3. Answers are short and factual but written as a complete sentence that restates the subject (e.g. "Reinhardt's Barrier Field has 1600 health."). One to three sentences maximum. Keep exact numbers, names, dates and results.
4. Vary the questions: factual lookups (who/what/when/where/how many), why/how questions, comparisons or lists when the passage supports them, and a few rephrasings of the same important fact with different wording.
5. For gameplay/balance facts (hero stats, ability numbers, patch changes), state the date or patch in the question or answer, e.g. "As of the June 16, 2026 patch, ..." when the passage gives a date; otherwise say "In the version described, ...". For esports results, name the tournament and year.
6. Language: English. No markdown, no numbering, no meta commentary.
7. Skip trivial or redundant pairs. Do not duplicate the same question.

Output JSON only: {"pairs":[{"question":"...","answer":"..."}]}"""

_stop = {"flag": False}


def _on_sigint(signum, frame):
    if _stop["flag"]:
        raise KeyboardInterrupt  # 2e Ctrl+C : abandonne la requete en cours
    _stop["flag"] = True
    tqdm.write("Ctrl+C : arret apres le chunk en cours (Ctrl+C encore pour abandonner)")


def load_chunks(only, source, exclude=()):
    # Chunks a faible valeur (memes regles que le filtrage) : on ne genere que la part `keep` qui sera conservee.
    from gen.build_dataset import _u, load_all, low_value_rule
    from scraper.common import title_matches
    _, cats = load_all()
    chunks, skipped = [], 0
    with open(CHUNKS, encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if only == "nonsensitive" and c["sensitive"]:
                continue
            if only == "sensitive" and not c["sensitive"]:
                continue
            if (source and c["source"] != source) or (exclude and title_matches(c["title"], exclude)):
                continue
            pc = cats.get((c["source"], int(c["id"].split(":")[1])), [])
            r = low_value_rule(c["title"], {x.lower() for x in pc}, c["section"])
            if r and _u("gen|" + c["id"]) >= r["keep"]:
                skipped += 1
                continue
            chunks.append(c)
    if skipped:
        tqdm.write(f"{skipped} chunks a faible valeur ignores")
    order = {"fandom": 0, "liquipedia": 1}
    chunks.sort(key=lambda c: (order.get(c["source"], 9), -c["words"]))
    return chunks


def done_keys(path):
    keys = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    keys.add((r["id"], r["revid"]))
                except (json.JSONDecodeError, KeyError):
                    pass
    return keys


def call_model(model, text, num_predict):
    body = {
        "model": model, "stream": False, "think": False, "format": SCHEMA, "keep_alive": "30m",
        "options": {"num_predict": num_predict, "temperature": 0.7},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "Passage:\n\n" + text}],
    }
    r = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=300)
    r.raise_for_status()
    d = r.json()
    data = json.loads(d["message"]["content"])
    pairs = []
    for p in data.get("pairs", []):
        q, a = str(p.get("question", "")).strip(), str(p.get("answer", "")).strip()
        if q and a:
            pairs.append({"question": q, "answer": a})
    if not pairs:
        raise ValueError("aucune paire valide")
    return pairs, d.get("eval_count", 0), d.get("eval_duration", 0) / 1e9


def suspend_windows():
    ps = ("Add-Type -AssemblyName System.Windows.Forms; "
          "[System.Windows.Forms.Application]::SetSuspendState("
          "[System.Windows.Forms.PowerState]::Suspend, $false, $false)")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps])


def parse_until(s):
    h, m = map(int, s.split(":"))
    now = dt.datetime.now()
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t > now else t + dt.timedelta(days=1)


def run(model=DEFAULT_MODEL, only="nonsensitive", source=None, limit=None, until=None,
        max_chunks=None, sleep_after=False, num_predict=2000, exclude=()):
    QA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = QA_DIR / f"gen_{model.replace(':', '_').replace('/', '_')}.jsonl"
    err_path = QA_DIR / "errors.jsonl"
    stop_file = QA_DIR / "STOP"
    until_dt = parse_until(until) if until else None
    chunks = load_chunks(only, source, exclude)
    if limit:
        chunks = chunks[:limit]
    done = done_keys(out_path)
    todo = [c for c in chunks if (c["id"], c["revid"]) not in done]
    print(f"{len(chunks)} chunks selectionnes, {len(chunks) - len(todo)} deja faits, "
          f"{len(todo)} a faire -> {out_path}")
    signal.signal(signal.SIGINT, _on_sigint)

    n_done = n_pairs = n_tok = 0
    t_gen = 0.0
    reason = "termine"
    bar = tqdm(todo, unit="chunk")
    try:
        with open(out_path, "a", encoding="utf-8") as out:
            for c in bar:
                if _stop["flag"]:
                    reason = "ctrl-c"
                    break
                if stop_file.exists():
                    reason = "fichier STOP"
                    break
                if until_dt and dt.datetime.now() >= until_dt:
                    reason = "--until atteint"
                    break
                if max_chunks and n_done >= max_chunks:
                    reason = "--max-chunks atteint"
                    break
                res = None
                last_err = ""
                for attempt in range(3):
                    t0 = time.time()
                    try:
                        res = call_model(model, c["text"], num_predict) + (time.time() - t0,)
                        break
                    except (requests.RequestException, ValueError, KeyError) as e:
                        last_err = f"{type(e).__name__}: {e}"
                        tqdm.write(f"essai {attempt + 1}/3 echoue ({c['id']}): {last_err}")
                        time.sleep(5 * (attempt + 1))
                if res is None:
                    with open(err_path, "a", encoding="utf-8") as ef:
                        ef.write(json.dumps({"id": c["id"], "revid": c["revid"], "error": last_err,
                                             "ts": dt.datetime.now().isoformat()}) + "\n")
                    continue
                pairs, toks, gen_s, wall = res
                out.write(json.dumps({
                    "id": c["id"], "revid": c["revid"], "source": c["source"], "title": c["title"],
                    "section": c["section"], "sensitive": c["sensitive"], "pairs": pairs,
                    "seconds": round(wall, 2), "tokens": toks}, ensure_ascii=False) + "\n")
                out.flush()
                n_done += 1
                n_pairs += len(pairs)
                n_tok += toks
                t_gen += gen_s
                bar.set_postfix(pairs=n_pairs, tps=f"{n_tok / t_gen:.0f}" if t_gen else "-")
    except KeyboardInterrupt:
        reason = "ctrl-c (requete abandonnee)"
    finally:
        bar.close()
    remaining = len(todo) - n_done
    print(f"Arret: {reason}. Chunks faits: {n_done}, restants (selection): {remaining}, "
          f"paires: {n_pairs}, tok/s moyen: {n_tok / t_gen:.1f}" if t_gen else
          f"Arret: {reason}. Chunks faits: 0, restants: {remaining}")
    if sleep_after and reason in ("termine", "--until atteint", "--max-chunks atteint"):
        print("Mise en veille...")
        suspend_windows()
