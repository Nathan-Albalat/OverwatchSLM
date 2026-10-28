"""Chemins, chargement des configs / du jeu de test, helpers JSONL partages."""
import hashlib
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"
TEST_SET = EVAL / "test_set.jsonl"
RUNS = EVAL / "runs"
JUDGMENTS = EVAL / "judgments"
REVIEW = EVAL / "review"
REPORT = EVAL / "report"
COVERAGE = ROOT / "data" / "dataset" / "test_coverage.jsonl"
CONFIGS = Path(__file__).resolve().parent / "configs.toml"
STOP_FILE = RUNS / "STOP"


def use_set(name):
    """`--set dev` : jeu de developpement (eval/dev_set.jsonl) avec ses propres runs, jugements et rapport sous
    eval/dev/, pour regler les variantes sans regarder le jeu de test. A appeler avant d'importer run/judge/report."""
    global TEST_SET, RUNS, JUDGMENTS, REVIEW, REPORT, COVERAGE, STOP_FILE
    if name == "test":
        return
    if name not in ("dev", "player"):
        raise SystemExit(f"jeu inconnu: {name} (test | dev | player)")
    # player : questions posees par de vrais joueurs (eval/player_set.jsonl), sorties sous eval/player/
    base = EVAL / name
    TEST_SET = EVAL / ("dev_set.jsonl" if name == "dev" else "player_set.jsonl")
    RUNS, JUDGMENTS = base / "runs", base / "judgments"
    REVIEW, REPORT, STOP_FILE = base / "review", base / "report", base / "runs" / "STOP"
    COVERAGE = base / "no_coverage.jsonl"     # pas de couverture : paires val, jamais vues a l'entrainement
    if not TEST_SET.exists():
        raise SystemExit(f"{TEST_SET} absent" + (" : lancer `rag.cli devset`" if name == "dev" else ""))


def qhash(q):
    return hashlib.sha1((q["question"] + q["answer"]).encode("utf-8")).hexdigest()[:12]


def load_test(path=None):
    qs = read_jsonl(path or TEST_SET)
    for q in qs:
        q["qhash"] = qhash(q)
    return qs


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_configs():
    with open(CONFIGS, "rb") as f:
        data = tomllib.load(f)
    defaults = data.get("defaults", {})
    return {c["name"]: defaults | c for c in data.get("config", [])}


def get_config(name):
    cfgs = load_configs()
    if name not in cfgs:
        raise SystemExit(f"configuration inconnue: {name} (disponibles: {', '.join(cfgs)})")
    return cfgs[name]


def latest_by_id(rows):
    """Derniere ligne par id (les relances / rejugements s'ajoutent en fin de fichier)."""
    d = {}
    for r in rows:
        d[r["id"]] = r
    return d
