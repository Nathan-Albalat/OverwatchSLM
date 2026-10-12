import argparse


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="ow-scrape")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fandom", "liquipedia"):
        sp = sub.add_parser(name, help=f"collecte {name}")
        sp.add_argument("--limit", type=int, default=None, help="nb max de pages au total (tests)")
        sp.add_argument("--first", action="append", default=[],
                        help="titre a traiter en priorite (repetable, utile avec --limit)")
        sp.add_argument("--refresh", action="store_true",
                        help="compare les revid au brut et ne re-telecharge que les pages modifiees/nouvelles")
        sp.add_argument("--dry-run", action="store_true",
                        help="avec --refresh : liste les pages modifiees sans rien ecrire")
        sp.add_argument("--only-title", action="append", default=[],
                        help="avec --refresh : ne traite que ce titre et ses sous-pages Titre/... (repetable)")
        sp.add_argument("--out-dir", default=None,
                        help="repertoire du pages.jsonl (defaut data/raw/<source>) ; utile pour tester")
    bz = sub.add_parser("blizzard", help="notes de patch officielles (page mensuelle) -> data/raw/blizzard")
    bz.add_argument("--month", action="append", required=True, help="AAAA/MM (repetable), ex. 2026/10")
    sub.add_parser("clean", help="nettoie les donnees brutes")
    sub.add_parser("stats", help="volumetrie")
    sub.add_parser("chunk", help="decoupe data/clean en chunks")
    g = sub.add_parser("generate", help="genere les paires Q/R via Ollama (reprenable)")
    g.add_argument("--model", default="qwen3.6:35b-a3b")
    g.add_argument("--only", choices=["nonsensitive", "sensitive", "all"], default="nonsensitive")
    g.add_argument("--source", choices=["fandom", "liquipedia", "blizzard"], default=None)
    g.add_argument("--limit", type=int, default=None, help="ne considere que les N premiers chunks de la selection")
    g.add_argument("--max-chunks", type=int, default=None, help="max de chunks generes dans ce run")
    g.add_argument("--until", default=None, help="HH:MM : arret entre deux chunks a cette heure")
    g.add_argument("--sleep-after", action="store_true", help="mise en veille Windows a la fin")
    g.add_argument("--exclude-title", action="append", default=[],
                   help="ignore les chunks de ce titre et de ses sous-pages (repetable)")
    sub.add_parser("templates", help="Q/R deterministes (infobox, MVP) -> data/qa/templates.jsonl")
    b = sub.add_parser("build-dataset", help="filtre/dedoublonne les Q/R, exporte train/val/cpt (lecture seule des QA)")
    b.add_argument("--include-sensitive", action="store_true",
                   help="garde les paires de chunks sensibles (heroes/patchs) et les stats heros")
    b.add_argument("--test-threshold", type=int, default=None, help="seuil token_set_ratio vs test (defaut 85)")
    b.add_argument("--val-pct", type=int, default=5)
    b.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if args.cmd == "fandom":
        from . import fandom
        fandom.run(args.limit, args.first, args.refresh, args.dry_run, args.out_dir, args.only_title)
    elif args.cmd == "liquipedia":
        from . import liquipedia
        liquipedia.run(args.limit, args.first, args.refresh, args.dry_run, args.out_dir, args.only_title)
    elif args.cmd == "blizzard":
        from . import blizzard
        blizzard.run(args.month)
    elif args.cmd == "clean":
        from . import clean
        clean.run()
    elif args.cmd == "stats":
        from . import stats
        stats.run()
    elif args.cmd == "chunk":
        from . import chunk
        chunk.run()
    elif args.cmd == "generate":
        from gen import generate
        generate.run(args.model, args.only, args.source, args.limit, args.until,
                     args.max_chunks, args.sleep_after, exclude=args.exclude_title)
    elif args.cmd == "templates":
        from gen import templates
        templates.run()
    elif args.cmd == "build-dataset":
        from gen import build_dataset
        build_dataset.run(args.include_sensitive, args.test_threshold, args.val_pct, args.seed)


if __name__ == "__main__":
    main()
