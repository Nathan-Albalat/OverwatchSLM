"""CLI d'entrainement : `python -m train.cli run|export|list|summary` (a lancer dans WSL, sauf list/summary)."""
import argparse
import json

from train.common import ROOT, TRAIN_DIR, load_runs


def cmd_list(a):
    for name, c in load_runs().items():
        rd = TRAIN_DIR / name
        etat = ("exporte" if (rd / "gguf" / "model.gguf").exists() else "entraine" if (rd / "adapter").exists()
                else "checkpoints" if (rd / "checkpoints").exists() else "-")
        print(f"{name:20s} {c['model']:22s} {c['stage']:5s} epochs={c['epochs']} lr={c['lr']} "
              f"packing={c['packing']} data={c['data']}" + (f" init={c['init_from']}" if c.get("init_from") else "")
              + f"  [{etat}]")


def cmd_run(a):
    from train.run import train
    train(a.name, resume=a.resume, max_steps=a.max_steps, limit=a.limit, tag=a.tag, data=a.data,
          val_data=a.val_data, init_from=a.init_from, save_every=a.save_every, eval_every=a.eval_every)


def cmd_export(a):
    from train.export import export
    export(a.name, quant=a.quant, tag=a.tag)


def cmd_summary(a):
    rows = []
    for p in sorted(TRAIN_DIR.glob("*/train_stats.json")):
        rows.append(json.loads(p.read_text(encoding="utf-8")))
    out = ROOT / "eval" / "report" / "training.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    f = lambda v, nd=3: "-" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))
    L = ["# Entrainements QLoRA (Unsloth + TRL)", "",
         "Genere par `python -m train.cli summary` a partir de `data/train/*/train_stats.json`.", "",
         "| run | modele | etape | exemples | ecartes (trop longs) | pas | tokens vus (total / reponse) | temps (min) | s/ex | tok/s "
         "| VRAM pic (Go) | loss train | loss val |", "|" + "---|" * 13]
    for s in rows:
        L.append(f"| {s['run']} | {s['model'].split('/')[-1]} | {s['stage']}{' (init ' + s['init_from'] + ')' if s.get('init_from') else ''} "
                 f"| {s['train_examples']} | {s['dropped_too_long']} | {s['steps']} | {s['tokens_seen_total_est']} / "
                 f"{s['tokens_seen_completion_est']} | {s['train_seconds'] / 60:.1f} | {f(s['s_per_example'])} | {f(s['tokens_per_s'])} "
                 f"| {f(s['peak_vram_gb'], 2)} | {f(s['train_loss_final'])} | {f(s['val_loss_final'])} |")
    L += ["", "Hyperparametres communs : LoRA r=32 alpha=32 sur 7 modules, batch 4 x accumulation 4, AdamW 8 bits, cosine, bf16.",
          "Les runs suffixes `-smoke` sont des tests de validation du code (quelques pas), pas des entrainements complets.", ""]
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"{out} ({len(rows)} runs)")


def main():
    ap = argparse.ArgumentParser(prog="train")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("name")
    r.add_argument("--resume", action="store_true")
    r.add_argument("--max-steps", type=int)
    r.add_argument("--limit", type=int, help="sous-echantillon deterministe de l'entrainement")
    r.add_argument("--tag", help="suffixe du repertoire de sortie (ex. smoke -> data/train/<name>-smoke)")
    r.add_argument("--data")
    r.add_argument("--val-data")
    r.add_argument("--init-from", help="nom du run dont on reprend l'adapter (avec son suffixe eventuel)")
    r.add_argument("--save-every", type=int)
    r.add_argument("--eval-every", type=int)
    r.set_defaults(fn=cmd_run)
    e = sub.add_parser("export")
    e.add_argument("name")
    e.add_argument("--quant", default="q4_k_m")
    e.add_argument("--tag")
    e.set_defaults(fn=cmd_export)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("summary").set_defaults(fn=cmd_summary)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
