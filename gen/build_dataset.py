"""Filtrage, dedoublonnage et export du dataset d'entrainement (SFT chat + CPT).

LECTURE SEULE sur data/qa/*, data/chunks, data/clean : peut etre relance a tout moment, y compris pendant
qu'une generation ecrit (derniere ligne incomplete ignoree). Ecrit uniquement dans data/dataset/.

Etapes (comptes dans stats.json) :
  stale        : chunk absent ou revid different du chunk actuel (paires obsoletes apres refresh)
  sensitive    : chunks sensibles / stats heros ecartes (sauf --include-sensitive)
  format       : question/reponse vides ou trop courtes/longues
  meta         : « according to the passage », « in this passage »... (question ou reponse)
  low_value    : categories/pages a faible valeur (LOW_VALUE_RULES, configurable ; keep = part conservee)
  anchoring    : les nombres de la reponse doivent apparaitre dans le chunk source (paires LLM)
  dedup_exact  : meme question normalisee (la premiere est gardee ; templates avant LLM)
  dedup_fuzzy  : questions quasi identiques (rapidfuzz ratio >= FUZZY_DEDUP) au sein d'une meme page
  test_overlap : question trop proche (rapidfuzz token_set_ratio >= TEST_THRESHOLD) d'une question de
                 eval/test_set.jsonl (toutes, y compris unanswerable) -> supprimee

Couverture du test (indicatif, test_coverage.jsonl) : une question du test (hors unanswerable) est
« couverte » si, parmi les paires FINALES (train+val), il existe
  (a) une paire dont la question a token_set_ratio >= COVER_Q_SIM avec la question du test ET fuzz.ratio >= COVER_RATIO
      ET memes nombres ET >= 60 % des cles et des mots de contenu de la question du test, OU
  (b) une paire dont question+reponse contiennent >= 75 % des « cles » de la reponse attendue ET >= 50 %
      des cles de la question du test. Cles = nombres + mots capitalises (hors mots interrogatifs/outils),
      en minuscules ; les cles trop frequentes (> 3 % des paires) sont ignorees.
Comme les paires trop proches du test ont ete retirees, (a) ne capte que les reformulations lointaines et
(b) l'essentiel : un fait est « couvert » s'il est enonce par au moins une paire d'entrainement.
"""
import csv
import glob
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from rapidfuzz import fuzz, process

from scraper.config import SOURCES

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "data" / "chunks" / "chunks.jsonl"
CLEAN = ROOT / "data" / "clean"
QA_DIR = ROOT / "data" / "qa"
TEST = ROOT / "eval" / "test_set.jsonl"
OUT_DIR = ROOT / "data" / "dataset"

SYSTEM_PROMPT = ("You are an expert on the video game Overwatch (lore, heroes, maps, patches and esports). "
                 "Answer accurately and concisely. If you do not know the answer, or the question rests on a "
                 "false premise, say so instead of guessing.")

TEST_THRESHOLD = 80     # token_set_ratio question de paire vs question du test (voir calibration)
MIN_RATIO = 70          # ... ET fuzz.ratio >= 70 (evite « keybind de Hanzo » ~ « ultime de Hanzo »)
KEY_OVERLAP = 0.6       # ... ET au moins 60 % des cles (entites/nombres) de la question du test dans celle de la paire
COVER_Q_SIM = 75        # seuil (a) de couverture (token_set_ratio ; fuzz.ratio >= COVER_RATIO)
COVER_RATIO = 65
FUZZY_DEDUP = 92
MIN_Q, MAX_Q, MIN_A, MAX_A = 12, 400, 2, 700

META_RE = re.compile(
    r"according to (the|this) (passage|text|description|article|page|wiki|excerpt|section)|"
    r"\b(in|from|by) (the|this) (passage|text|article|excerpt)\b|"
    r"\b(the|this) (passage|excerpt)\b|\bthe (page|article) (states|says|mentions)\b", re.I)

# Regles de faible valeur (configurables). Une paire/chunk correspond a une regle si l'un des criteres
# (titre regex, categories exactes en minuscules, section regex) est vrai. `keep` = fraction conservee
# (0.0 = tout ecarter ; echantillonnage deterministe par hash de l'identifiant).
LOW_VALUE_RULES = [
    {"name": "cosmetic_lists", "keep": 0.0,
     "title": r"(^|/)(cosmetics|heroes skins|sprays|emotes|player icons|player titles|highlight intros|"
              r"voice lines|weapon charms|souvenirs|nameplates?)$",
     "cats": {"hero cosmetics pages", "event cosmetics pages", "cosmetics"},
     "section": r"(^|> )(skins?|cosmetics?|sprays?|emotes?|voice lines?|highlight intros?|"
                r"player (titles|icons)|weapon charms?)( |$|>)"},
    {"name": "battle_pass_tiers", "keep": 0.0, "title": r"^battle pass$",
     "section": r"battle pass|prestige tiers|(free|premium) track|\btiers? \d"},
    {"name": "transcripts", "keep": 0.15, "title": r"transcript$", "cats": {"transcripts"},
     "section": r"transcript"},
    {"name": "voice_quotes", "keep": 0.1, "title": r"/quotes$", "cats": {"quotations"}},
    {"name": "event_challenges", "keep": 0.15, "title": r"challenge$"},
    {"name": "achievements", "keep": 0.25, "title": r"^achievements$"},
]

# Plafond des paires templates de tournois (~33k sinon, majoritairement de petits tournois) : on garde tous
# les grands circuits et un echantillon deterministe des autres.
MAJOR_TOURNAMENT_RE = re.compile(r"^(Overwatch League|Overwatch Champions Series|Overwatch World Cup|"
                                 r"Overwatch Contenders|Esports World Cup|Overwatch APEX)", re.I)
MINOR_TOURNAMENT_CAP = 1500

# categorie « metier » d'une page (pour les stats) : (etiquette, categories wiki en minuscules, regex titre)
CATEGORY_RULES = [
    ("patch", {"patches"}, r"patch$"),
    ("hero", {"heroes", "stadium hero pages"}, None),
    ("map", {"maps", "game modes"}, None),
    ("player", {"players"}, None),
    ("team", {"teams", "overwatch league teams"}, None),
    ("tournament", {"tournaments", "online tournaments", "finished tournaments"}, None),
    ("story", {"hero story pages", "short stories", "comics", "origin stories", "transcripts"}, None),
    ("event", {"limited-time events", "seasonal events"}, None),
]

STOP_CAP = set("""what which who whom whose when where why how is are was were do does did can could in on at of
for to the a an and or if as by with from it its this that these those there their his her he she they overwatch
name year true false yes no under during after before into about between has have will would should
list give tell explain describe""".split())


# ------------------------------------------------------------------ utilitaires

def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def _u(s):
    """Hash deterministe dans [0,1)."""
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16) / 0x100000000


def _numbers(s):
    out = set()
    for m in re.findall(r"\d+(?:[.,]\d+)*", s):
        out.add(re.sub(r"(?<=\d),(?=\d)", "", m).rstrip(".,"))
    return out


def _read_jsonl(path):
    """Lecture tolerante (derniere ligne eventuellement incomplete) -> (liste, nb_lignes_ignorees)."""
    out, bad = [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    return out, bad


def page_category(cats, title):
    lc = {c.lower() for c in cats}
    for label, cs, rx in CATEGORY_RULES:
        if lc & cs or (rx and re.search(rx, title, re.I)):
            return label
    return "other"


def low_value_rule(title, cats_lc, section):
    for r in LOW_VALUE_RULES:
        if (r.get("title") and re.search(r["title"], title, re.I)) or \
                (r.get("cats") and cats_lc & r["cats"]) or \
                (r.get("section") and section and re.search(r["section"], section, re.I)):
            return r
    return None


FUNC = set("""what which who whom whose when where why how is are was were do does did can could the a an of in
on at to for and or by with as it its this that these those there their his her he she they s overwatch
from has have been be""".split())


def _content(s):
    return {w for w in _norm(s).split() if w not in FUNC}


def _close(pq, tq, ratio_min):
    """Meme fait demande ? ratio >= ratio_min, memes nombres, >= 60 % des cles et des mots de contenu de la
    question du test retrouves dans la question de la paire."""
    if fuzz.ratio(_norm(pq), _norm(tq)) < ratio_min:
        return False
    nt, np_ = _numbers(tq), _numbers(pq)
    if nt and not nt <= np_:
        return False
    kt = _keys(tq)
    if kt and len(kt & _keys(pq)) / len(kt) < KEY_OVERLAP:
        return False
    ct = _content(tq)
    return not ct or len(ct & _content(pq)) / len(ct) >= KEY_OVERLAP


def _keys(s):
    ks = {n for n in _numbers(s)}
    for w in re.findall(r"\b[A-Z][\w'.:\-]*", s):
        w = w.rstrip(".:'-").lower().replace("'s", "")
        if len(w) > 1 and w not in STOP_CAP:
            ks.add(w)
    return ks


# ------------------------------------------------------------------ chargement

def load_all():
    chunks, cats = {}, {}
    with open(CHUNKS, encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            chunks[c["id"]] = c
    for src in SOURCES:
        p = CLEAN / f"{src}.jsonl"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    cats[(src, r["pageid"])] = r["categories"]
    return chunks, cats


def load_pairs(info):
    """Paires templates puis LLM (ordre = priorite pour le dedoublonnage)."""
    pairs = []
    tp = QA_DIR / "templates.jsonl"
    if tp.exists():
        recs, bad = _read_jsonl(tp)
        for r in recs:
            pairs.append({**r, "kind": "template", "section": "", "pageid": int(r["id"].split(":")[2])})
        info["templates_file"] = len(recs)
    info["gen_files"] = {}
    for gp in sorted(glob.glob(str(QA_DIR / "gen_*.jsonl"))):
        recs, bad = _read_jsonl(gp)
        info["gen_files"][Path(gp).name] = {"chunks": len(recs), "lignes_ignorees": bad}
        for r in recs:
            for i, p in enumerate(r.get("pairs", [])):
                q, a = str(p.get("question", "")).strip(), str(p.get("answer", "")).strip()
                pairs.append({"id": f"{r['id']}#{i}", "source": r["source"], "title": r["title"],
                              "chunk_id": r["id"], "revid": r["revid"], "kind": "llm", "pageid": int(r["id"].split(":")[1]),
                              "section": r.get("section", ""), "sensitive": bool(r.get("sensitive")),
                              "question": q, "answer": a})
    return pairs


# ------------------------------------------------------------------ pipeline

def run(include_sensitive=False, test_threshold=None, val_pct=5, seed=0):
    T = test_threshold or TEST_THRESHOLD
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    info = {}
    chunks, cats = load_all()
    pairs = load_pairs(info)
    test, _ = _read_jsonl(TEST)
    stages = []

    def stage(name, kept, extra=None):
        prev = stages[-1]["kept"] if stages else None
        e = {"stage": name, "kept": len(kept), "removed": (prev - len(kept)) if prev is not None else 0}
        if extra:
            e.update(extra)
        stages.append(e)
        print(f"{name:14s} garde {len(kept):7d}  retire {e['removed']:6d}" + (f"  {extra}" if extra else ""))
        return kept

    stage("raw", pairs, {"llm": sum(p["kind"] == "llm" for p in pairs),
                         "template": sum(p["kind"] == "template" for p in pairs)})

    # 1. obsolescence (revid) : les chunks sans chunk_id (templates sur pages non chunkees) restent
    cur = []
    for p in pairs:
        cid = p.get("chunk_id")
        if cid is None:
            cur.append(p)
        elif cid in chunks and chunks[cid]["revid"] == p["revid"]:
            cur.append(p)
    pairs = stage("stale", cur)

    # 2. sensibles
    if not include_sensitive:
        # templates : seul leur propre drapeau compte (stats heros) ; LLM : sensibilite du chunk source
        pairs = stage("sensitive", [p for p in pairs if not (
            p["sensitive"] or (p["kind"] == "llm" and chunks[p["chunk_id"]]["sensitive"]))])
    else:
        stage("sensitive", pairs, {"note": "inclus"})

    # 3. format
    pairs = stage("format", [p for p in pairs if MIN_Q <= len(p["question"]) <= MAX_Q
                             and MIN_A <= len(p["answer"]) <= MAX_A and re.search(r"[A-Za-z]", p["question"])])

    # 4. phrases meta
    pairs = stage("meta", [p for p in pairs if not META_RE.search(p["question"]) and not META_RE.search(p["answer"])])

    # 5. faible valeur
    lv = Counter()
    kept = []
    for p in pairs:
        pc = cats.get((p["source"], p["pageid"]), [])
        p["category"] = p.get("category") if p["kind"] == "template" else page_category(pc, p["title"])
        r = low_value_rule(p["title"], {c.lower() for c in pc}, p["section"])
        # LLM : meme tirage par chunk que generate.py (le chunk genere est garde en entier) ; templates : par paire
        key = "gen|" + p["chunk_id"] if p["kind"] == "llm" else "lv|" + p["id"]
        if r and _u(key) >= r["keep"]:
            lv[r["name"]] += 1
            continue
        kept.append(p)
    pairs = stage("low_value", kept, {"par_regle": dict(lv),
                                      "keep": {r["name"]: r["keep"] for r in LOW_VALUE_RULES}})

    # 5 bis. plafond des templates de petits tournois
    minor = [p for p in pairs if p["kind"] == "template" and p["category"] == "tournament"
             and not MAJOR_TOURNAMENT_RE.search(p["title"])]
    minor_keep = {p["id"] + "|" + p["question"] for p in
                  sorted(minor, key=lambda p: _u("tc|" + p["id"] + "|" + p["question"]))[:MINOR_TOURNAMENT_CAP]}
    pairs = stage("tournament_cap", [p for p in pairs if not (
        p["kind"] == "template" and p["category"] == "tournament" and not MAJOR_TOURNAMENT_RE.search(p["title"])
        and p["id"] + "|" + p["question"] not in minor_keep)],
        {"minor_cap": MINOR_TOURNAMENT_CAP, "minor_avant": len(minor)})

    # 6. ancrage des nombres (paires LLM)
    kept, cache = [], {}
    for p in pairs:
        if p["kind"] == "llm":
            cid = p["chunk_id"]
            if cid not in cache:
                cache[cid] = _numbers(chunks[cid]["text"])
            if not _numbers(p["answer"]) <= cache[cid]:
                continue
        kept.append(p)
    pairs = stage("anchoring", kept)

    # 7. dedoublonnage exact puis flou (par page)
    seen, kept = set(), []
    for p in pairs:
        k = _norm(p["question"])
        if k in seen:
            continue
        seen.add(k)
        kept.append(p)
    pairs = stage("dedup_exact", kept)
    byp = defaultdict(list)
    kept = []
    for p in pairs:
        key = (p["source"], p["title"])
        lst = byp[key]
        if lst and process.extractOne(_norm(p["question"]), lst, scorer=fuzz.ratio,
                                      score_cutoff=FUZZY_DEDUP) is not None:
            continue
        lst.append(_norm(p["question"]))
        kept.append(p)
    pairs = stage("dedup_fuzzy", kept)

    # 8. proximite avec le jeu de test : token_set_ratio >= T ET ratio >= MIN_RATIO ET memes entites/nombres.
    # (token_set_ratio seul est domine par la structure de la question : « What is X's ultimate ability? »
    # est a 91 pour tout autre heros ; le critere des cles evite de retirer des faits differents.)
    tq = [_norm(t["question"]) for t in test]
    removed_ex, kept, hist = [], [], Counter()
    n_score_only = 0
    for p in pairs:
        nq = _norm(p["question"])
        cands = process.extract(nq, tq, scorer=fuzz.token_set_ratio, limit=None, score_cutoff=T)
        if cands:
            n_score_only += 1
        hit = next(((sc, i) for _, sc, i in sorted(cands, key=lambda x: -x[1])
                    if _close(p["question"], test[i]["question"], MIN_RATIO)), None)
        if hit:
            if len(removed_ex) < 60:
                removed_ex.append({"pair_question": p["question"], "pair_answer": p["answer"], "kind": p["kind"],
                                   "test_id": test[hit[1]]["id"], "test_question": test[hit[1]]["question"],
                                   "score": round(hit[0], 1)})
            continue
        kept.append(p)
    pairs = stage("test_overlap", kept, {"threshold": T, "min_ratio": MIN_RATIO, "key_overlap": KEY_OVERLAP,
                                         "pairs_above_threshold_score_only": n_score_only})

    # ------------------------------------------------------------------ export
    rng = random.Random(seed)
    for p in pairs:
        p["split"] = "val" if int(hashlib.md5(f"{p['source']}|{p['title']}".encode()).hexdigest()[:8], 16) % 100 < val_pct else "train"
    sets = {"train": [], "val": []}
    for p in pairs:
        sets[p["split"]].append(p)
    for name, lst in sets.items():
        rng.shuffle(lst)
        with open(OUT_DIR / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for p in lst:
                f.write(json.dumps({"messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": p["question"]},
                    {"role": "assistant", "content": p["answer"]}]}, ensure_ascii=False) + "\n")
    # paires finales avec metadonnees (point de depart des exemples RAFT : deja filtrees, hors test)
    with open(OUT_DIR / "pairs.jsonl", "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps({k: p.get(k) for k in ("id", "kind", "source", "title", "category", "chunk_id", "revid",
                                                      "split", "sensitive", "question", "answer")},
                               ensure_ascii=False) + "\n")
    sample = rng.sample(pairs, min(100, len(pairs)))
    with open(OUT_DIR / "sample_review.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["kind", "source", "category", "title", "section", "chunk_id", "question", "answer", "verdict"])
        for p in sample:
            w.writerow([p["kind"], p["source"], p["category"], p["title"], p["section"], p["chunk_id"] or "",
                        p["question"], p["answer"], ""])

    # CPT : texte brut des chunks non vides, hors faible valeur (et hors sensibles par defaut)
    n_cpt = n_skip_lv = n_skip_s = 0
    with open(OUT_DIR / "cpt.jsonl", "w", encoding="utf-8") as f:
        for c in chunks.values():
            if not c["text"].strip():
                continue
            if c["sensitive"] and not include_sensitive:
                n_skip_s += 1
                continue
            pc = cats.get((c["source"], int(c["id"].split(":")[1])), [])
            if low_value_rule(c["title"], {x.lower() for x in pc}, c["section"]):
                n_skip_lv += 1
                continue
            f.write(json.dumps({"text": c["text"]}, ensure_ascii=False) + "\n")
            n_cpt += 1
    print(f"CPT: {n_cpt} chunks (ecartes: {n_skip_lv} faible valeur, {n_skip_s} sensibles)")

    cov = coverage(test, pairs)

    stats = {
        "inputs": info, "include_sensitive": include_sensitive, "stages": stages,
        "test_overlap": {"threshold": T, "removed": stages[-1]["removed"], "examples": removed_ex,
                         "key_overlap": KEY_OVERLAP, "min_ratio": MIN_RATIO, "pairs_above_threshold_score_only": n_score_only},
        "final": {"pairs": len(pairs), "train": len(sets["train"]), "val": len(sets["val"]),
                  "by_source": dict(Counter(p["source"] for p in pairs)),
                  "by_category": dict(Counter(p["category"] for p in pairs)),
                  "by_kind": dict(Counter(p["kind"] for p in pairs)),
                  "by_source_kind": dict(Counter(f"{p['source']}/{p['kind']}" for p in pairs))},
        "cpt": {"chunks": n_cpt, "skipped_low_value": n_skip_lv, "skipped_sensitive": n_skip_s},
        "test_coverage": cov["summary"],
    }
    with open(OUT_DIR / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"Final: {len(pairs)} paires (train {len(sets['train'])}, val {len(sets['val'])}) -> {OUT_DIR}")
    print("Couverture du test:", json.dumps(cov["summary"], ensure_ascii=False))


# ------------------------------------------------------------------ couverture du test

def coverage(test, pairs):
    pq = [_norm(p["question"]) for p in pairs]
    pk = [_keys(p["question"] + " " + p["answer"]) for p in pairs]
    df = Counter(k for ks in pk for k in ks)
    generic = {k for k, v in df.items() if v > 0.03 * max(1, len(pairs))}
    index = defaultdict(list)
    for i, ks in enumerate(pk):
        for k in ks - generic:
            index[k].append(i)
    rows = []
    for t in test:
        if t["category"] == "unanswerable":
            continue
        kq_all = _keys(t["question"])
        qs, qi = 0, None
        for _, sc, i in process.extract(_norm(t["question"]), pq, scorer=fuzz.token_set_ratio, limit=None,
                                        score_cutoff=COVER_Q_SIM):
            if sc > qs and _close(pairs[i]["question"], t["question"], COVER_RATIO):
                qs, qi = sc, i
        m = (None, qs, qi) if qi is not None else None
        ka = _keys(t["answer"]) - generic
        kq = kq_all - generic
        best, best_sc = None, 0.0
        if ka and kq:
            cand = Counter(i for k in kq for i in index.get(k, ()))
            for i in cand:
                ra = len(ka & pk[i]) / len(ka)
                rq = len(kq & pk[i]) / len(kq)
                if ra >= 0.75 and rq >= 0.5 and ra + rq > best_sc:
                    best, best_sc = i, ra + rq
        by_q, by_e = qs >= COVER_Q_SIM, best is not None
        sup = pairs[best] if by_e else (pairs[m[2]] if m and by_q else None)
        rows.append({"id": t["id"], "category": t["category"], "temporal": t["temporal"],
                     "covered": by_q or by_e,
                     "reason": "+".join(r for r, ok in (("question_sim", by_q), ("entities", by_e)) if ok) or "none",
                     "best_question_sim": round(qs, 1),
                     "support": {"question": sup["question"], "answer": sup["answer"], "title": sup["title"],
                                 "kind": sup["kind"]} if sup else None})
    with open(OUT_DIR / "test_coverage.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def agg(sel):
        rs = [r for r in rows if sel(r)]
        return {"n": len(rs), "covered": sum(r["covered"] for r in rs)}
    cats = sorted({r["category"] for r in rows})
    summary = {"questions": len(rows), "covered": sum(r["covered"] for r in rows),
               "by_reason": dict(Counter(r["reason"] for r in rows)),
               "by_category": {c: agg(lambda r, c=c: r["category"] == c) for c in cats},
               "temporal": agg(lambda r: r["temporal"]), "non_temporal": agg(lambda r: not r["temporal"]),
               "params": {"cover_q_sim": COVER_Q_SIM, "answer_keys_min": 0.75, "question_keys_min": 0.5}}
    return {"summary": summary, "rows": rows}
