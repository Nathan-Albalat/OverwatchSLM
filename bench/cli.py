import argparse
from pathlib import Path


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="ow-bench")
    ap.add_argument("--set", default="test", choices=["test", "dev", "player"],
                    help="dev = eval/dev_set.jsonl, sorties sous eval/dev/ (reglages sans toucher au test)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="pose les questions du test a une ou plusieurs configurations (reprenable)")
    r.add_argument("configs", nargs="+")
    r.add_argument("--limit", type=int, default=None, help="nb max de questions posees dans ce run")
    r.add_argument("--ids", default=None, help="ids separes par des virgules (ex. G01,P03)")
    r.add_argument("--category", default=None)

    j = sub.add_parser("judge", help="LLM-juge par lots sur les reponses d'une configuration")
    j.add_argument("configs", nargs="+")
    j.add_argument("--judge", default="claude_cli:sonnet", help="backend:modele (claude_cli:sonnet, ollama:qwen3.6:35b-a3b)")
    j.add_argument("--runs-dir", default=None, help="dossier des runs (defaut eval/runs ; utile pour tester)")
    j.add_argument("--out-dir", default=None, help="dossier des jugements (defaut eval/judgments)")

    p = sub.add_parser("report", help="tableaux du rapport -> eval/report/")
    p.add_argument("configs", nargs="*")
    p.add_argument("--judge", default=None, help="ne garde que les jugements de ce juge")

    v = sub.add_parser("review-export", help="echantillon stratifie pour verification manuelle")
    v.add_argument("--per-config", type=int, default=15)
    v.add_argument("--judge", default=None)

    e = sub.add_parser("export-questions", help="backend manual : CSV des questions a poser")
    e.add_argument("config")
    i = sub.add_parser("import-answers", help="backend manual : relit le CSV rempli")
    i.add_argument("config")
    i.add_argument("csv")

    sub.add_parser("list", help="liste les configurations")
    a = ap.parse_args()
    from bench import common as C
    C.use_set(a.set)

    if a.cmd == "run":
        from bench.run import run
        run(a.configs, a.limit, a.ids.split(",") if a.ids else None, a.category)
    elif a.cmd == "judge":
        from bench import common as C
        from bench.judge import judge
        judge(a.configs, a.judge, Path(a.runs_dir) if a.runs_dir else C.RUNS,
              Path(a.out_dir) if a.out_dir else C.JUDGMENTS)
    elif a.cmd == "report":
        from bench.report import build
        build(a.configs or None, a.judge)
    elif a.cmd == "review-export":
        from bench.report import review_export
        review_export(a.per_config, judge=a.judge)
    elif a.cmd == "export-questions":
        from bench.run import export_questions
        export_questions(a.config)
    elif a.cmd == "import-answers":
        from bench.run import import_answers
        import_answers(a.config, a.csv)
    elif a.cmd == "list":
        from bench import common as C
        for n, c in C.load_configs().items():
            print(f"{n:20s} {c['backend']:11s} {c['model']}" + (f" rag={c['rag']}" if c.get("rag") else ""))


if __name__ == "__main__":
    main()
