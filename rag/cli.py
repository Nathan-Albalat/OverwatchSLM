import argparse
import sys


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="ow-rag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    modes = ["bm25", "dense", "hybrid"]

    i = sub.add_parser("index", help="construit docs.jsonl, bm25.pkl et (hybrid) les embeddings (reprenable)")
    i.add_argument("--mode", choices=["bm25", "hybrid"], default="hybrid")
    i.add_argument("--embed-model", default="qwen3-embedding:0.6b")
    i.add_argument("--batch", type=int, default=32)
    i.add_argument("--max-words", type=int, default=450, help="troncature des textes a l'encodage (0 = aucune)")
    i.add_argument("--no-truncate", action="store_true", help="n'autorise pas Ollama a tronquer")

    e = sub.add_parser("eval", help="qualite de la recherche sans LLM (hit@k) -> eval/report/retrieval.md")
    e.add_argument("--mode", choices=modes, default=None)
    e.add_argument("--k", default="1,3,5,10")
    e.add_argument("--val-n", type=int, default=1000)
    e.add_argument("--out", default=None)

    r = sub.add_parser("raft", help="exemples RAFT -> data/dataset/raft_{train,val}.jsonl (reprenable)")
    r.add_argument("--n", type=int, default=15000)
    r.add_argument("--k", type=int, default=4)
    r.add_argument("--p-oracle", type=float, default=0.8)
    r.add_argument("--mode", choices=modes, default=None)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out-dir", default=None)
    r.add_argument("--template-share", type=float, default=0.1)
    r.add_argument("--max-words", type=int, default=400, help="troncature des passages")

    g = sub.add_parser("augment", help="corrections RAFT par LLM local : paraphrase | verify | apply | compose | noisy | apply3 | hard | teach | apply4 (reprenable)")
    g.add_argument("step", choices=["paraphrase", "verify", "apply", "compose", "noisy", "apply3", "hard", "teach", "apply4"])
    g.add_argument("--dir", default=None, help="dossier de travail/sortie (defaut raft_v2 ; raft_v3 pour compose|apply3)")
    g.add_argument("--src", default="data/dataset/raft_v2", help="v3 : dossier des raft_{train,val}_final.jsonl de depart")
    g.add_argument("--limit", type=int, default=None, help="v3 : nombre d'exemples (essais)")
    g.add_argument("--share-noisy", type=float, default=0.15, help="v3 : part des exemples non-refus bruites")
    g.add_argument("--share", type=float, default=None,
                   help="paraphrase : part reformulee (defaut 0.5) ; compose : part composee des oracles (defaut 0.3)")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--n", type=int, default=5000, help="v4 hard : nombre de graines")
    g.add_argument("--share-player", type=float, default=0.3, help="v4 hard : part des questions en registre joueur")
    g.add_argument("--props", default=None, help="v4 hard : proportions de graines, ex. hero=0.3,patch=0.3,map=0.2,esport=0.2")
    g.add_argument("--mix", type=int, default=None, help="v4 apply4 : exemples raft_v2 melanges (defaut : autant que de nouveaux)")
    g.add_argument("--val-total", type=int, default=300, help="v4 apply4 : taille visee de raft_val_final")
    g.add_argument("--mode", choices=["bm25", "dense", "hybrid"], default=None,
                   help="v4 hard : recherche des passages lies (bm25 : pas de modele d'embeddings a cote du 35B)")

    dv = sub.add_parser("devset", help="eval/dev_set.jsonl : paires val reformulees + questions sans reponse (LLM)")
    dv.add_argument("--n", type=int, default=300)
    dv.add_argument("--unanswerable", type=int, default=30)
    dv.add_argument("--seed", type=int, default=0)

    q = sub.add_parser("query", help="affiche les passages retournes pour une question")
    q.add_argument("question")
    q.add_argument("--k", type=int, default=5)
    q.add_argument("--mode", choices=modes, default=None)
    q.add_argument("--chars", type=int, default=300)

    a = ap.parse_args()
    if a.cmd == "index":
        from rag import index
        index.run(a.mode, a.embed_model, a.batch, a.max_words, not a.no_truncate)
    elif a.cmd == "eval":
        from rag import evaluate
        evaluate.run(a.mode, [int(x) for x in a.k.split(",")], a.val_n, a.out)
    elif a.cmd == "raft":
        from rag import raft
        raft.run(a.n, a.k, a.p_oracle, a.mode, a.seed, a.out_dir, a.template_share, a.max_words)
    elif a.cmd == "augment":
        from rag import augment
        d = a.dir or ("data/dataset/raft_v3" if a.step in ("compose", "noisy", "apply3") else
                      "data/dataset/raft_v4" if a.step in ("hard", "teach", "apply4") else "data/dataset/raft_v2")
        {"paraphrase": lambda: augment.paraphrase(d, 0.5 if a.share is None else a.share, a.seed),
         "verify": lambda: augment.verify(d), "apply": lambda: augment.apply(d),
         "compose": lambda: augment.compose(d, a.src, 0.3 if a.share is None else a.share, a.seed, a.limit),
         "noisy": lambda: augment.noisy(a.src, a.limit, a.share_noisy, a.seed),
         "apply3": lambda: augment.apply3(d, a.src, a.share_noisy, a.seed),
         "hard": lambda: augment.hard(d, a.n, a.seed, a.share_player,
                                      {k: float(v) for k, v in (x.split("=") for x in a.props.split(","))} if a.props else None,
                                      a.limit, a.mode),
         "teach": lambda: augment.teach(d, a.limit),
         "apply4": lambda: augment.apply4(d, a.src, a.mix, a.seed, a.limit, a.val_total)}[a.step]()
    elif a.cmd == "devset":
        from rag import augment
        augment.devset(a.n, a.unanswerable, a.seed)
    elif a.cmd == "query":
        from rag.retrieve import retrieve
        for n, p in enumerate(retrieve(a.question, a.k, a.mode), 1):
            txt = " ".join(p["text"].split())
            print(f"[{n}] {p['id']}  ({p['title']} | {p['section']})  score={p['score']}\n    {txt[:a.chars]}")


if __name__ == "__main__":
    main()
