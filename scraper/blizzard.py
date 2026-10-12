"""Notes de patch officielles Blizzard (page mensuelle) -> data/raw/blizzard/pages.jsonl.

Une page par patch, texte deja structure en titres Markdown (le chunker coupe par section) :
  # titre du patch / ## section (Hero Updates, Tank, Support...) / ### heros, carte / #### capacite.
pageid = AAAAMMJJ du patch ; revid = hash du texte (un changement de texte relance la generation).
Les pages deja presentes sont remplacees (pas d'historique a garder).
"""
import datetime as dt
import hashlib
import html
import json
import re

import requests

from .config import BLIZZARD_LICENSE, BLIZZARD_PATCH_NOTES, RAW, USER_AGENT

OUT = RAW / "blizzard" / "pages.jsonl"

_TAGS = [
    (r'<h3 class="PatchNotes-patchTitle">', "\n\n# "),
    (r'<h4 class="PatchNotes-sectionTitle">', "\n\n## "),
    (r'<h5 class="PatchNotesHeroUpdate-name">', "\n\n### "),
    (r'<div class="PatchNotesAbilityUpdate-name">', "\n\n#### "),
    (r'<div class="PatchNotesGeneralUpdate-title">', "\n\n#### "),
    (r"<li[^>]*>", "\n- "),
    (r"</?(?:p|br|div|ul|h\d)[^>]*>", "\n\n"),
]


def to_text(block):
    b = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", "", block)
    for pat, rep in _TAGS:
        b = re.sub(pat, rep, b)
    b = html.unescape(re.sub(r"<[^>]+>", "", b)).replace("\xa0", " ")
    b = re.sub(r"[ \t]+", " ", b)
    b = re.sub(r" ?\n ?", "\n", b)
    b = re.sub(r"\n(- [^\n]*)\n\n(?=- )", r"\n\1\n", b)      # listes compactes
    b = re.sub(r"\n{3,}", "\n\n", b)
    return b.strip()


def parse_month(page_html, url):
    pages = []
    for block in re.split(r'(?=<div class="PatchNotes-patch )', page_html)[1:]:
        m = re.search(r'PatchNotes-patchTitle">[^<]*?(\w+ \d{1,2}, \d{4})', block)
        if not m:
            continue
        date = dt.datetime.strptime(m.group(1), "%B %d, %Y").date()
        text = to_text(block)
        # retire la date isolee et le titre « # Overwatch Retail Patch Notes – ... » (redondants avec le titre de page)
        text = re.sub(r"^\w+ \d{1,2}, \d{4}\s*\n+", "", text)
        text = re.sub(r"^# [^\n]*\n+", "", text)
        title = f"{date:%B} {date.day}, {date.year} Patch (official notes)"
        pages.append({
            "pageid": int(f"{date:%Y%m%d}"), "title": title, "url": url,
            "revid": int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16),
            "categories": ["Patches"], "date": date.isoformat(), "text": text,
            "license": BLIZZARD_LICENSE,
        })
    return pages


def run(months):
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    old = {}
    if OUT.exists():
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                old[r["pageid"]] = r
    pages = dict(old)
    for month in months:
        url = BLIZZARD_PATCH_NOTES.format(month=month)
        r = s.get(url, timeout=60)
        r.raise_for_status()
        found = parse_month(r.text, url)
        for p in found:
            st = "nouvelle" if p["pageid"] not in old else (
                "modifiee" if old[p["pageid"]]["revid"] != p["revid"] else "inchangee")
            print(f"  {st}: {p['title']} ({len(p['text'].split())} mots)")
            pages[p["pageid"]] = p
        print(f"{month}: {len(found)} patchs")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for pid in sorted(pages):
            f.write(json.dumps(pages[pid], ensure_ascii=False) + "\n")
    tmp.replace(OUT)
    print(f"{len(pages)} pages -> {OUT}")
