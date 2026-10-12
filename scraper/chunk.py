import json
import re
from collections import Counter

from .config import CLEAN, DATA, SOURCES

CHUNKS = DATA / "chunks" / "chunks.jsonl"
MIN_CHUNK_WORDS = 60
TARGET, MAX_WORDS = 450, 600
SOFT_MIN = 250

SENSITIVE_CATS = {"heroes", "stadium hero pages", "patches", "patch"}
SKIP_HEADINGS = re.compile(
    r"^(external links?|references?|gallery|cosmetics?|voice ?lines?|voice actors?|"
    r"voice cast|sprays?|skins?|emotes?|highlight intros?|see also|navigation|trivia videos?)$", re.I)


def _wc(s):
    return len(s.split())


def _is_sensitive(rec):
    cats = {c.strip().lower() for c in rec.get("categories", [])}
    return bool(cats & SENSITIVE_CATS) or rec["title"].strip().endswith("Patch")


def _blocks(text):
    """[(chemin_section, texte_bloc, est_titre_h2_ou_h3)] ; ecarte les sections inutiles."""
    stack = []  # [(niveau, titre)]
    skip_level = None
    out = []
    for para in re.split(r"\n{2,}", text):
        para = para.strip()
        if not para:
            continue
        m = re.match(r"(#+) (.*)", para)
        if m:
            lvl, title = len(m.group(1)), m.group(2).strip()
            if skip_level is not None and lvl <= skip_level:
                skip_level = None
            if skip_level is None and SKIP_HEADINGS.match(title):
                skip_level = lvl
            stack = [s for s in stack if s[0] < lvl] + [(lvl, title)]
        if skip_level is not None:
            continue
        path = " > ".join(t for _, t in stack)
        out.append((path, para, bool(m and len(m.group(1)) <= 3)))
    return out


def _split_long(para):
    """Coupe un bloc > MAX_WORDS sur ses lignes."""
    parts, cur, n = [], [], 0
    for ln in para.split("\n"):
        w = _wc(ln)
        if cur and n + w > TARGET:
            parts.append("\n".join(cur))
            cur, n = [], 0
        cur.append(ln)
        n += w
    if cur:
        parts.append("\n".join(cur))
    return parts


def chunk_page(rec):
    blocks = []
    for path, para, is_h in _blocks(rec["text"]):
        if _wc(para) > MAX_WORDS:
            blocks += [(path, p, False) for p in _split_long(para)]
        else:
            blocks.append((path, para, is_h))
    groups, cur, n = [], [], 0
    for b in blocks:
        w = _wc(b[1])
        if cur and (n + w > MAX_WORDS or (b[2] and n >= SOFT_MIN) or n + w > TARGET and n >= SOFT_MIN):
            groups.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += w
    if cur:
        groups.append(cur)
    res = []
    for g in groups:
        body = "\n\n".join(b[1] for b in g)
        # un groupe ne contenant que des titres n'a pas d'interet
        if _wc(re.sub(r"^#+ .*$", "", body, flags=re.M)) < MIN_CHUNK_WORDS:
            continue
        path = next((b[0] for b in g if not b[1].startswith("#")), g[0][0])
        head = f"Page: {rec['title']}" + (f"\nSection: {path}" if path else "")
        res.append((path, f"{head}\n\n{body}"))
    return res


def run():
    CHUNKS.parent.mkdir(parents=True, exist_ok=True)
    cnt = Counter()
    with open(CHUNKS, "w", encoding="utf-8") as out:
        for src in SOURCES:
            p = CLEAN / f"{src}.jsonl"
            if not p.exists():
                continue
            with open(p, encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    sens = _is_sensitive(rec)
                    for i, (path, text) in enumerate(chunk_page(rec)):
                        out.write(json.dumps({
                            "id": f"{src}:{rec['pageid']}:{i}", "revid": rec.get("revid"),
                            "source": src, "title": rec["title"], "section": path,
                            "url": rec["url"], "sensitive": sens, "words": _wc(text), "text": text,
                        }, ensure_ascii=False) + "\n")
                        cnt[(src, sens)] += 1
    tot = 0
    for (src, sens), n in sorted(cnt.items()):
        print(f"{src:11s} {'sensible' if sens else 'non sensible':13s} {n}")
        tot += n
    print(f"total: {tot} chunks -> {CHUNKS}")
