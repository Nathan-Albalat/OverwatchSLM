"""ow-bench report / review-export : agregation des runs + jugements en tableaux (Markdown + CSV)."""
import csv
import statistics
from collections import Counter, defaultdict

from bench import common as C

SCORE = {"correct": 1.0, "partial": 0.5}
CATS = ["lore", "gameplay", "esport", "patch", "maps_modes", "unanswerable"]
VERDICTS = ["correct", "partial", "incorrect", "abstained", "hallucinated"]


def pct(values, q):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    k = (len(v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def _fmt(x, nd=1, suffix=""):
    return "n/a" if x is None else f"{x:.{nd}f}{suffix}"


def score_pct(rows):
    return 100 * sum(SCORE.get(r["verdict"], 0.0) for r in rows) / len(rows) if rows else None


def load_coverage():
    cov = {c["id"]: c["covered"] for c in C.read_jsonl(C.COVERAGE)}
    return cov or None


def load_records(names, judge=None, runs_dir=C.RUNS, judg_dir=C.JUDGMENTS):
    """{config: [ {q, run, verdict, reason} ]} ; seules les reponses jugees et a jour sont retenues."""
    qmap = {q["id"]: q for q in C.load_test()}
    out = {}
    for name in names:
        runs = C.latest_by_id(C.read_jsonl(runs_dir / f"{name}.jsonl"))
        judg = {}
        for j in C.read_jsonl(judg_dir / f"{name}.jsonl"):
            if judge and j.get("judge") != judge:
                continue
            judg[(j["id"], j["qhash"], j["run_ts"])] = j
        recs = []
        for i, r in runs.items():
            q = qmap.get(i)
            j = judg.get((i, r["qhash"], r["ts"]))
            if q and q["qhash"] == r["qhash"] and j:
                recs.append({"q": q, "run": r, "verdict": j["verdict"], "reason": j.get("reason", "")})
        if recs:
            out[name] = recs
    return out


def _md(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _write_csv(name, headers, rows):
    C.REPORT.mkdir(parents=True, exist_ok=True)
    with open(C.REPORT / f"{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(headers)
        w.writerows(rows)


def cohen_kappa(a, b):
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def agreement(review_path=None):
    path = review_path or (C.REVIEW / "sample.csv")
    if not path.exists():
        return None
    judge, human = [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            h = (r.get("human_verdict") or "").strip().lower()
            if h:
                judge.append(r["judge_verdict"])
                human.append(h)
    if not judge:
        return None
    return {"n": len(judge), "agree_pct": 100 * sum(x == y for x, y in zip(judge, human)) / len(judge),
            "kappa": cohen_kappa(judge, human)}


def build(names=None, judge=None):
    names = names or sorted(p.stem for p in C.RUNS.glob("*.jsonl"))
    data = load_records(names, judge)
    if not data:
        raise SystemExit("aucune reponse jugee : lancer `ow-bench run` puis `ow-bench judge`")
    cov = load_coverage()
    md = ["# Rapport du banc d'evaluation OW-SLM", "",
          "Score : correct = 1, partial = 0.5, le reste = 0. Jeu de test fige : `eval/test_set.jsonl`.",
          "Sources du corpus : Overwatch Fandom wiki (CC-BY-SA) et Liquipedia Overwatch (CC-BY-SA 3.0, "
          "attribution obligatoire).", ""]

    # 1. global
    h = ["config", "n", "score global %", "score repondables %", "correct", "partial", "incorrect",
         "abstained", "hallucinated"]
    rows = []
    for name, recs in data.items():
        ans = [r for r in recs if r["q"]["category"] != "unanswerable"]
        c = Counter(r["verdict"] for r in recs)
        rows.append([name, len(recs), _fmt(score_pct(recs)), _fmt(score_pct(ans))] + [c[v] for v in VERDICTS[:5]])
    md += ["## Exactitude globale", "", _md(h, rows), ""]
    _write_csv("global", h, rows)

    # 2. par categorie
    h = ["config"] + CATS
    rows = []
    for name, recs in data.items():
        row = [name]
        for cat in CATS:
            sub = [r for r in recs if r["q"]["category"] == cat]
            row.append(f"{_fmt(score_pct(sub))} (n={len(sub)})")
        rows.append(row)
    md += ["## Par categorie (score %)", "", _md(h, rows), ""]
    _write_csv("categories", h, rows)

    # 3. temporel / couvert (hors unanswerable : le score y mesure autre chose)
    h = ["config", "temporel", "non temporel", "couvert", "non couvert"]
    rows = []
    for name, recs in data.items():
        ans = [r for r in recs if r["q"]["category"] != "unanswerable"]
        t = [r for r in ans if r["q"]["temporal"]]
        nt = [r for r in ans if not r["q"]["temporal"]]
        if cov:
            cv = [r for r in ans if cov.get(r["q"]["id"]) is True]
            nc = [r for r in ans if cov.get(r["q"]["id"]) is False]
            cvs, ncs = f"{_fmt(score_pct(cv))} (n={len(cv)})", f"{_fmt(score_pct(nc))} (n={len(nc)})"
        else:
            cvs = ncs = "n/a"
        rows.append([name, f"{_fmt(score_pct(t))} (n={len(t)})", f"{_fmt(score_pct(nt))} (n={len(nt)})", cvs, ncs])
    md += ["## Temporel / couvert (questions repondables, score %)", "",
           _md(h, rows), "",
           "Couvert = fait du test retrouve dans le dataset d'entrainement (`data/dataset/test_coverage.jsonl`, "
           "heuristique indicative)." + ("" if cov else " Fichier absent : colonnes n/a."), ""]
    _write_csv("temporal_coverage", h, rows)

    # 4. hallucination / abstention
    h = ["config", "n unanswerable", "taux d'hallucination %", "n repondables", "taux d'abstention %"]
    rows = []
    for name, recs in data.items():
        un = [r for r in recs if r["q"]["category"] == "unanswerable"]
        ans = [r for r in recs if r["q"]["category"] != "unanswerable"]
        hal = 100 * sum(r["verdict"] == "hallucinated" for r in un) / len(un) if un else None
        ab = 100 * sum(r["verdict"] == "abstained" for r in ans) / len(ans) if ans else None
        rows.append([name, len(un), _fmt(hal), len(ans), _fmt(ab)])
    md += ["## Hallucination et abstention", "", _md(h, rows), ""]
    _write_csv("hallucination", h, rows)

    # 5. performance
    h = ["config", "latence p50 s", "latence p95 s", "ttft p50 s", "tok/s median", "VRAM Mo", "cout/requete USD"]
    rows = []
    for name, recs in data.items():
        runs = [r["run"] for r in recs]
        lat = [r["latency_s"] for r in runs]
        vr = [r["vram_mb"] for r in runs if r["vram_mb"]]
        costs = [r["cost_usd"] or 0.0 for r in runs]
        rows.append([name, _fmt(pct(lat, 0.5), 2), _fmt(pct(lat, 0.95), 2),
                     _fmt(pct([r["ttft_s"] for r in runs], 0.5), 2),
                     _fmt(pct([r["tok_s"] for r in runs], 0.5), 1),
                     _fmt(max(vr) if vr else None, 0), _fmt(statistics.mean(costs), 4)])
    md += ["## Performance", "", _md(h, rows), "",
           "Local : cout = 0. Claude : cout = equivalent API (abonnement, pas une depense reelle). "
           "Pour `claude_cli`, tok/s et latence sont indicatifs (reseau inclus, tokens de reflexion inclus). "
           "VRAM lue via Ollama (`/api/ps`), pas `nvidia-smi`.", ""]
    _write_csv("performance", h, rows)

    # 6. accord juge / humain
    ag = agreement()
    md += ["## Accord juge / verification manuelle", ""]
    if ag:
        md += [f"Echantillon verifie : {ag['n']} reponses ; accord {ag['agree_pct']:.1f} % ; "
               f"kappa de Cohen {ag['kappa']:.2f}." if ag["kappa"] is not None else f"{ag['n']} reponses.", ""]
    else:
        md += ["Pas encore de verification manuelle (`ow-bench review-export`, puis remplir `human_verdict`).", ""]
    md += ["## Cout de mise a jour (Saison 5)", "",
           "A renseigner manuellement (pages re-scrapees, minutes de generation et d'entrainement).", ""]

    C.REPORT.mkdir(parents=True, exist_ok=True)
    (C.REPORT / "report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Rapport ecrit dans {C.REPORT / 'report.md'} ({len(data)} configurations)")


def review_export(per_config=15, names=None, judge=None, seed=0):
    import random
    names = names or sorted(p.stem for p in C.JUDGMENTS.glob("*.jsonl"))
    data = load_records(names, judge)
    rng = random.Random(seed)
    C.REVIEW.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, recs in data.items():
        by_v = defaultdict(list)
        for r in recs:
            by_v[r["verdict"]].append(r)
        for lst in by_v.values():
            rng.shuffle(lst)
        picked = []
        while len(picked) < min(per_config, len(recs)):   # tour de role entre verdicts (stratification)
            for lst in by_v.values():
                if lst and len(picked) < per_config:
                    picked.append(lst.pop())
        for r in picked:
            rows.append([name, r["q"]["id"], r["q"]["category"], r["q"]["question"], r["q"]["answer"],
                         r["run"]["text"], r["verdict"], r["reason"], ""])
    path = C.REVIEW / "sample.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["config", "id", "category", "question", "reference", "model_answer", "judge_verdict",
                    "judge_reason", "human_verdict"])
        w.writerows(rows)
    print(f"{len(rows)} lignes ecrites dans {path} (remplir human_verdict avec les memes etiquettes)")
