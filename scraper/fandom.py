import json
from pathlib import Path

from tqdm import tqdm

from .client import MediaWikiClient
from .common import done_ids, list_pages, merge_refresh, plan_refresh
from .config import FANDOM_API, FANDOM_DELAY, RAW

OUT = RAW / "fandom" / "pages.jsonl"


def _fetch(client, pid, title):
    d = client.get({"action": "parse", "pageid": pid, "prop": "text|categories|revid"})
    if "parse" not in d:
        print(f"skip {pid} {title}: {d.get('error')}")
        return None
    p = d["parse"]
    return {"pageid": pid, "title": p.get("title", title), "revid": p.get("revid"),
            "categories": [c["category"] for c in p.get("categories", []) if not c.get("hidden")],
            "html": p["text"]}


def run(limit=None, first=(), refresh=False, dry_run=False, out_dir=None, only=()):
    out = Path(out_dir) / "pages.jsonl" if out_dir else OUT
    client = MediaWikiClient(FANDOM_API, FANDOM_DELAY)
    if refresh or dry_run:
        return _refresh(client, out, limit, first, dry_run, only)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages = list_pages(client)
    print(f"Fandom: {len(pages)} articles listes")
    done = done_ids(out)
    todo = [p for p in pages if p[0] not in done]
    todo.sort(key=lambda p: p[1] not in first)  # titres prioritaires en tete (tests)
    if limit is not None:
        todo = todo[:max(0, limit - len(done))]
    print(f"Deja recuperes: {len(done)} ; a telecharger: {len(todo)}")
    with open(out, "a", encoding="utf-8") as f:
        for pid, title in tqdm(todo):
            rec = _fetch(client, pid, title)
            if rec:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()


def _refresh(client, out, limit, first, dry_run, only=()):
    todo, deleted = plan_refresh(client, out, "Fandom", dry_run, limit, first, only)
    if dry_run:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    new_path = out.with_name("pages.refresh.jsonl")  # reprenable : les ids deja presents sont sautes
    done = done_ids(new_path)
    todo = [p for p in todo if p[0] not in done]
    print(f"A re-telecharger: {len(todo)} (deja dans {new_path.name}: {len(done)})")
    with open(new_path, "a", encoding="utf-8") as f:
        for pid, title in tqdm(todo):
            rec = _fetch(client, pid, title)
            if rec:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
    got = done_ids(new_path)
    merge_refresh(out, new_path, got | (deleted if limit is None else set()))
