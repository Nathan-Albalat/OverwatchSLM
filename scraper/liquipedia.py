import json
from pathlib import Path

from tqdm import tqdm

from .client import MediaWikiClient
from .common import done_ids, list_pages, merge_refresh, plan_refresh
from .config import LIQUI_API, LIQUI_DELAY, RAW

OUT = RAW / "liquipedia" / "pages.jsonl"
BATCH = 50


def _download(client, todo, titles, f):
    with tqdm(total=len(todo)) as bar:
        for i in range(0, len(todo), BATCH):
            pending = [p[0] for p in todo[i:i + BATCH]]
            got = set()
            rounds = 0
            # Reponses volumineuses : contenu pagine via rvcontinue. On re-demande
            # les pages restees sans contenu jusqu'a les avoir toutes.
            while pending and rounds < 20:
                rounds += 1
                for d in client.query_all({
                        "prop": "revisions|categories", "rvprop": "content|ids|timestamp",
                        "rvslots": "main", "cllimit": "max", "clshow": "!hidden",
                        "pageids": "|".join(map(str, pending))}):
                    for p in d.get("query", {}).get("pages", []):
                        pid = p.get("pageid")
                        revs = p.get("revisions")
                        if pid is None or pid in got or not revs:
                            continue
                        rev = revs[0]
                        content = rev.get("slots", {}).get("main", {}).get("content")
                        if content is None:
                            continue
                        got.add(pid)
                        rec = {"pageid": pid, "title": p.get("title", titles.get(pid)),
                               "revid": rev.get("revid"), "timestamp": rev.get("timestamp"),
                               "categories": [c["title"].split(":", 1)[-1]
                                              for c in p.get("categories", [])],
                               "wikitext": content}
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f.flush()
                        bar.update(1)
                pending = [x for x in pending if x not in got]
            if pending:
                print(f"Pages non recuperees: {pending}")


def run(limit=None, first=(), refresh=False, dry_run=False, out_dir=None, only=()):
    out = Path(out_dir) / "pages.jsonl" if out_dir else OUT
    client = MediaWikiClient(LIQUI_API, LIQUI_DELAY)
    if refresh or dry_run:
        return _refresh(client, out, limit, first, dry_run, only)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages = list_pages(client)
    print(f"Liquipedia: {len(pages)} articles listes")
    done = done_ids(out)
    todo = [p for p in pages if p[0] not in done]
    todo.sort(key=lambda p: p[1] not in first)  # titres prioritaires en tete (tests)
    if limit is not None:
        todo = todo[:max(0, limit - len(done))]
    print(f"Deja recuperes: {len(done)} ; a telecharger: {len(todo)}")
    with open(out, "a", encoding="utf-8") as f:
        _download(client, todo, dict(pages), f)


def _refresh(client, out, limit, first, dry_run, only=()):
    todo, deleted = plan_refresh(client, out, "Liquipedia", dry_run, limit, first, only)
    if dry_run:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    new_path = out.with_name("pages.refresh.jsonl")  # reprenable : les ids deja presents sont sautes
    done = done_ids(new_path)
    todo = [p for p in todo if p[0] not in done]
    print(f"A re-telecharger: {len(todo)} (deja dans {new_path.name}: {len(done)})")
    with open(new_path, "a", encoding="utf-8") as f:
        _download(client, todo, dict(todo), f)
    got = done_ids(new_path)
    merge_refresh(out, new_path, got | (deleted if limit is None else set()))
