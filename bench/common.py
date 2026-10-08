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


def qhash(q):
    return hashlib.sha1((q["question"] + q["answer"]).encode("utf-8")).hexdigest()[:12]


def load_test(path=TEST_SET):
    qs = read_jsonl(path)
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
