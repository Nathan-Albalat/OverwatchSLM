import json
from pathlib import Path


def done_ids(path: Path) -> set:
    ids = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    ids.add(json.loads(line)["pageid"])
                except (json.JSONDecodeError, KeyError):
                    pass
    return ids


def list_pages_info(client):
    """{pageid: (title, lastrevid)} des articles ns0 non-redirections (une requete par 500 pages)."""
    out = {}
    for data in client.query_all({"generator": "allpages", "gapnamespace": 0,
                                  "gapfilterredir": "nonredirects", "gaplimit": "max",
                                  "prop": "info"}):
        for p in data.get("query", {}).get("pages", []):
            if "pageid" in p and p.get("lastrevid") is not None:
                out[p["pageid"]] = (p["title"], p["lastrevid"])
    return out


def load_revids(path: Path) -> dict:
    """{pageid: revid} du fichier brut (derniere occurrence)."""
    d = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    d[r["pageid"]] = r.get("revid")
                except (json.JSONDecodeError, KeyError):
                    pass
    return d


def title_matches(title, only):
    """Vrai si `only` est vide, ou si title vaut l'un des titres ou est une sous-page `Titre/...`."""
    return not only or any(title == o or title.startswith(o + "/") for o in only)


def plan_refresh(client, out_path: Path, label: str, dry_run: bool, limit=None, first=(), only=()):
    """Compare les revid du wiki a ceux du fichier brut.
    Retourne (todo [(pid, titre)], deleted {pid}) ; en dry-run affiche et ne touche a aucun fichier.
    `only` : restreint aux titres donnes (et sous-pages) ; aucune suppression n'est alors appliquee."""
    live = list_pages_info(client)
    old = load_revids(out_path)
    changed = [(pid, t) for pid, (t, rv) in live.items() if pid in old and old[pid] != rv and title_matches(t, only)]
    new = [(pid, t) for pid, (t, rv) in live.items() if pid not in old and title_matches(t, only)]
    deleted = set() if only else set(old) - set(live)
    if only:
        absent = [o for o in only if not any(title_matches(t, [o]) for t, _ in live.values())]
        if absent:
            print(f"  titres absents du wiki: {absent}")
    print(f"{label}: {len(live)} pages en ligne, {len(old)} dans le brut -> "
          f"{len(changed)} modifiees, {len(new)} nouvelles, {len(deleted)} supprimees/redirigees")
    todo = changed + new
    todo.sort(key=lambda p: p[1] not in first)
    if limit is not None:
        todo = todo[:limit]
    if dry_run:
        for pid, t in changed[:100]:
            print(f"  modifiee: {t} (revid {old[pid]} -> {live[pid][1]})")
        for pid, t in new[:10]:
            print(f"  nouvelle: {t}")
        print("dry-run : aucune ecriture")
    return todo, deleted


def merge_refresh(out_path: Path, new_path: Path, replaced: set):
    """Reecrit out_path sans les pages remplacees/supprimees, puis y ajoute new_path (remplacement atomique)."""
    import os
    tmp = out_path.with_suffix(".jsonl.tmp")
    n_old = n_new = 0
    with open(tmp, "w", encoding="utf-8") as w:
        if out_path.exists():
            with open(out_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        pid = json.loads(line)["pageid"]
                    except (json.JSONDecodeError, KeyError):
                        continue
                    if pid not in replaced:
                        w.write(line if line.endswith("\n") else line + "\n")
                        n_old += 1
        if new_path.exists():
            with open(new_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        w.write(line if line.endswith("\n") else line + "\n")
                        n_new += 1
    os.replace(tmp, out_path)
    new_path.unlink(missing_ok=True)
    print(f"Fusion: {n_old} pages conservees + {n_new} pages rafraichies -> {out_path}")


def list_pages(client):
    """Retourne [(pageid, title)] des articles ns0 non-redirections."""
    out = []
    for data in client.query_all({"list": "allpages", "apnamespace": 0,
                                  "apfilterredir": "nonredirects", "aplimit": "max"}):
        for p in data["query"]["allpages"]:
            out.append((p["pageid"], p["title"]))
    return out
