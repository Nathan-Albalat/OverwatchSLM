"""Export d'un adapter entraine -> GGUF (+ Modelfile Ollama). A executer dans WSL, cwd = ~/work (jamais dans le depot)."""
import glob
import os
import shutil
import time
from pathlib import Path, PureWindowsPath

from train.common import TMPL, get_run

THINK_OLD = '<|im_start|>assistant\n{{ end }}\n{{- end }}'
THINK_NEW = '<|im_start|>assistant\n<think>\n\n</think>\n\n{{ end }}\n{{- end }}'


def modelfile_text(gguf_name="model.gguf"):
    """TEMPLATE/PARAMETER du modele de base Ollama (train/modelfiles/qwen3.tmpl), avec le bloc <think> vide ajoute
    a l'amorce de reponse : c'est le format vu a l'entrainement (enable_thinking=False)."""
    tmpl = TMPL.read_text(encoding="utf-8")
    if THINK_OLD not in tmpl:
        raise SystemExit("qwen3.tmpl : amorce de reponse introuvable, adapter THINK_OLD")
    return f"FROM ./{gguf_name}\n" + tmpl.replace(THINK_OLD, THINK_NEW)


def export(run_name, quant="q4_k_m", tag=None):
    if str(Path.cwd()).startswith("/mnt/"):
        raise SystemExit("lancer l'export depuis ~/work (WSL), pas depuis /mnt/c : llama.cpp doit etre compile cote WSL")
    import unsloth  # noqa: F401
    from unsloth import FastLanguageModel

    cfg = get_run(run_name, tag)
    rd = cfg["run_dir"]
    adapter = rd / "adapter"
    if not adapter.exists():
        raise SystemExit(f"adapter introuvable : {adapter}")
    t0 = time.time()
    model, tok = FastLanguageModel.from_pretrained(str(adapter), max_seq_length=cfg["max_seq_length"],
                                                   load_in_4bit=cfg["load_in_4bit"])
    tmp = Path.home() / "work" / f"gguf_{cfg['run_name']}"
    shutil.rmtree(tmp, ignore_errors=True)
    model.save_pretrained_gguf(str(tmp), tok, quantization_method=quant)
    cands = [p for p in glob.glob(str(tmp) + "*/*.gguf") if "F16" not in os.path.basename(p).upper()]
    if not cands:
        raise SystemExit(f"aucun .gguf produit dans {tmp}")
    src = max(cands, key=os.path.getsize) if len(cands) > 1 else cands[0]
    out = rd / "gguf"
    out.mkdir(exist_ok=True)
    shutil.copyfile(src, out / "model.gguf")
    (out / "Modelfile").write_text(modelfile_text(), encoding="utf-8", newline="\n")
    size = (out / "model.gguf").stat().st_size / 1e9
    print(f"GGUF : {out / 'model.gguf'} ({size:.2f} Go, {time.time() - t0:.0f} s)")
    name = f"ow-{cfg['run_name']}"
    print("\nCote Windows (PowerShell) :")
    p = PureWindowsPath("data", "train", cfg["run_name"], "gguf", "Modelfile")
    print(f"  ollama create {name} -f {p}")
    return out
