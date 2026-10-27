"""Prepare un dossier (partage, cle USB...) contenant un projet pret a l'emploi pour le Mac :
- le code, exporte de git (`git archive HEAD` : fichiers suivis, sans l'historique) ;
- ce que git ne suit pas et dont la demo a besoin : index RAG (data/rag) et modeles fine-tunes (GGUF + Modelfile).
Le dossier obtenu a la meme arborescence que le depot. Voir docs/REPRISE_MAC.md.

Usage : python -m demo.bundle <dossier> [--runs qwen3-4b-raft-v2 qwen3-1.7b-raft] [--no-code] [--with-query-cache]
"""
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAG_FILES = ["docs.jsonl", "bm25.pkl", "emb.npy", "emb_ids.json"]
DEFAULT_RUNS = ["qwen3-4b-raft-v2", "qwen3-1.7b-raft"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def export_code(dest):
    """Code suivi par git au commit courant (les modifications non commitees ne sont pas incluses)."""
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        print("ATTENTION : modifications non commitees, absentes de l'export :\n" + dirty)
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    data = subprocess.run(["git", "archive", "--format=zip", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)
        n = len(z.namelist())
    print(f"Code exporte : commit {rev}, {n} fichiers")
    return rev


def copy(src, dest_root, manifest):
    rel = src.relative_to(ROOT)
    dst = dest_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        print(f"  deja present : {rel}")
    else:
        print(f"  copie : {rel} ({src.stat().st_size / 1e6:.0f} Mo)")
        shutil.copy2(src, dst)
    manifest[rel.as_posix()] = {"bytes": src.stat().st_size, "sha256": sha256(dst)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--runs", nargs="+", default=DEFAULT_RUNS)
    ap.add_argument("--no-code", action="store_true", help="donnees seulement (depot deja clone cote Mac)")
    ap.add_argument("--with-query-cache", action="store_true",
                    help="ajoute le cache d'embeddings des questions deja posees (~225 Mo)")
    a = ap.parse_args()
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    rev = None if a.no_code else export_code(dest)
    files = [ROOT / "data" / "rag" / f for f in RAG_FILES]
    if a.with_query_cache:
        files.append(ROOT / "data" / "rag" / "query_cache.jsonl")
    for run in a.runs:
        files += [ROOT / "data" / "train" / run / "gguf" / "model.gguf",
                  ROOT / "data" / "train" / run / "gguf" / "Modelfile"]
    missing = [f for f in files if not f.exists()]
    if missing:
        raise SystemExit("Fichiers absents : " + ", ".join(str(m.relative_to(ROOT)) for m in missing))
    manifest = {"_commit": rev, "_runs": a.runs}
    print(f"Donnees vers {dest} :")
    for f in files:
        copy(f, dest, manifest)
    (dest / "BUNDLE_MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    total = sum(m["bytes"] for k, m in manifest.items() if not k.startswith("_"))
    print(f"Termine : {total / 1e9:.2f} Go de donnees. Suite cote Mac : docs/REPRISE_MAC.md")


if __name__ == "__main__":
    main()
