import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIN_DIR = ROOT / "data" / "train"
CONFIGS = Path(__file__).resolve().parent / "configs.toml"
TMPL = Path(__file__).resolve().parent / "modelfiles" / "qwen3.tmpl"


def load_runs():
    d = tomllib.loads(CONFIGS.read_text(encoding="utf-8"))
    return {r["name"]: {**d.get("defaults", {}), **r} for r in d["run"]}


def get_run(name, tag=None):
    """Config d'un run ; `tag` (ex. 'smoke') donne un repertoire de sortie distinct <name>-<tag>."""
    runs = load_runs()
    if name not in runs:
        raise SystemExit(f"run inconnu : {name} (disponibles : {', '.join(runs)})")
    cfg = dict(runs[name])
    cfg["run_name"] = f"{name}-{tag}" if tag else name
    cfg["run_dir"] = TRAIN_DIR / cfg["run_name"]
    return cfg


def resolve(p):
    p = Path(p)
    return p if p.is_absolute() else ROOT / p
