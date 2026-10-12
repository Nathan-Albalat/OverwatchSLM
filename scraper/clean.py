import json
import re

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .wikitext import clean_wikitext
from .config import CLEAN, FANDOM_BASE, LICENSE, LIQUI_BASE, MIN_WORDS, RAW

# ---------------------------------------------------------------- Fandom (HTML)

SKIP_SELECTORS = [
    "script", "style", "noscript", "img", "svg", "figure", "figcaption", "video",
    "ul.gallery", ".gallery", ".navbox", ".navbox-container", "#toc", ".toc", ".mw-editsection",
    "sup", ".reference", ".mw-references-wrap", ".references", ".template-page-tabs",
    ".keyword-section", ".tooltip-contents", ".wds-tabs__wrapper", ".embedvideo",
    ".mw-empty-elt", ".noprint", ".hidden", "[style*='display:none']", ".pi-image-collection",
    ".ability-icon", ".image-wrapper", ".portable-infobox .pi-media-collection",
]
BLOCK = {"div", "p", "section", "aside", "dl", "dt", "dd", "blockquote", "center", "pre"}
HEADINGS = {"h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}


def _norm(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def _inline(el):
    """Texte d'un element en une ligne ; <br> devient '; '."""
    parts = []

    def rec(n):
        if isinstance(n, Comment):
            return
        if isinstance(n, NavigableString):
            parts.append(str(n))
        elif isinstance(n, Tag):
            if n.name == "br":
                parts.append(" ; ")
            else:
                for c in n.children:
                    rec(c)
                if n.name in ("p", "div", "li"):
                    parts.append(" ; ")

    rec(el)
    t = _norm("".join(parts))
    t = re.sub(r"(\s*;\s*)+", "; ", t).strip("; ").strip()
    return t


def _render(el, out):
    for c in el.children:
        if isinstance(c, Comment):
            continue
        if isinstance(c, NavigableString):
            out.append(str(c))
            continue
        if not isinstance(c, Tag):
            continue
        name = c.name
        cls = c.get("class") or []
        if name == "br":
            out.append("\n")
        elif name in HEADINGS:
            t = _norm(c.get_text(" "))
            out.append(f"\n\n{HEADINGS[name]} {t}\n\n" if t else "")
        elif name in ("ul", "ol"):
            out.append("\n")
            for i, li in enumerate(c.find_all("li", recursive=False), 1):
                sub = []
                _render(li, sub)
                t = _norm("".join(sub).replace("\n", " "))
                if t:
                    out.append(("- " if name == "ul" else f"{i}. ") + t + "\n")
            out.append("\n")
        elif name == "table":
            out.append("\n")
            for tr in c.find_all("tr"):
                cells = [_inline(td) for td in tr.find_all(["th", "td"], recursive=False)]
                cells = [x for x in cells if x]
                if cells:
                    out.append(" | ".join(cells) + "\n")
            out.append("\n")
        elif "data-row" in cls:
            h = c.select_one(".data-row-header")
            v = c.select_one(".data-row-value")
            if h and v:
                out.append(f"\n{_inline(h).rstrip(':')}: {_inline(v)}\n")
            else:
                out.append("\n" + _inline(c) + "\n")
        elif "type-block" in cls:
            h = c.select_one(".type-header")
            label = _inline(h) if h else "Type"
            if h:
                h.extract()
            out.append(f"\n{label}: {_inline(c)}\n")
        elif "cooldown" in cls:
            if _inline(c):
                out.append(f"\nCooldown: {_inline(c)}\n")
        elif "ability-key-main" in cls:
            out.append(f"\nKey: {_inline(c)}\n")
        elif "header" in cls and c.find_parent(class_="ability-box"):
            sub = c.select_one(".ability-key-main")
            if sub is not None:
                sub.extract()
            out.append(f"\n\n#### {_inline(c)}\n")
            if sub is not None:
                out.append(f"\nKey: {_inline(sub)}\n")
        elif "ability-details" in cls:
            out.append("\n\n")
            _render(c, out)
            out.append("\n\n")
        elif name in BLOCK or "wds-tab__content" in cls or "keyword" in cls:
            out.append("\n")
            _render(c, out)
            out.append("\n")
        else:
            _render(c, out)


def _infobox(aside):
    lines = []
    title = aside.select_one(".pi-title")
    if title:
        lines.append(f"Name: {_inline(title)}")
    for item in aside.select(".pi-data, .pi-header"):
        if "pi-header" in (item.get("class") or []):
            t = _inline(item)
            if t:
                lines.append(f"[{t}]")
            continue
        lab = item.select_one(".pi-data-label")
        val = item.select_one(".pi-data-value")
        if val is None:
            continue
        key = _inline(lab) if lab else item.get("data-source", "")
        v = _inline(val)
        if v:
            lines.append(f"{key}: {v}" if key else v)
    return "\n".join(lines)


def _tidy(text):
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # supprime les titres sans contenu (suivis d'un titre de niveau <= ou de la fin)
    lines = text.split("\n")
    out = []
    for i, ln in enumerate(lines):
        m = re.match(r"(#+) ", ln)
        if m:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                continue
            m2 = re.match(r"(#+) ", lines[j])
            if m2 and len(m2.group(1)) <= len(m.group(1)):
                continue
        out.append(ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _keys_to_text(root):
    for img in root.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if alt.startswith("Key "):
            img.replace_with("[" + alt[4:].strip() + "]")


def clean_fandom_html(html):
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one(".mw-parser-output") or soup
    _keys_to_text(root)
    for t in root.select("aside.portable-infobox sup, aside.portable-infobox .reference"):
        t.decompose()
    info_text = ""
    aside = root.select_one("aside.portable-infobox")
    if aside:
        info_text = _infobox(aside)
        aside.decompose()
    for sel in SKIP_SELECTORS:
        for t in root.select(sel):
            t.decompose()
    out = []
    _render(root, out)
    body = re.sub(r"[ \t]+", " ", "".join(out).replace("\xa0", " "))
    body = re.sub(r" ?\n ?", "\n", body)
    body = re.sub(r"^Example video:\s*$", "", body, flags=re.M)
    return _tidy((info_text + "\n\n" + body) if info_text else body)


def clean_fandom(rec):
    return {
        "source": "fandom", "pageid": rec["pageid"], "title": rec["title"],
        "url": FANDOM_BASE + rec["title"].replace(" ", "_"),
        "categories": [c.replace("_", " ") for c in rec.get("categories", [])],
        "revid": rec.get("revid"), "text": clean_fandom_html(rec["html"]), "license": LICENSE,
    }


# ----------------------------------------------------------- Liquipedia (wikitext)


def clean_liquipedia(rec):
    return {
        "source": "liquipedia", "pageid": rec["pageid"], "title": rec["title"],
        "url": LIQUI_BASE + rec["title"].replace(" ", "_"),
        "categories": rec.get("categories", []), "revid": rec.get("revid"),
        "text": clean_wikitext(rec["wikitext"], _tidy), "license": LICENSE,
    }


# ------------------------------------------------------- Blizzard (deja en texte)

def clean_blizzard(rec):
    return {
        "source": "blizzard", "pageid": rec["pageid"], "title": rec["title"], "url": rec["url"],
        "categories": rec.get("categories", []), "revid": rec.get("revid"),
        "text": _tidy(rec["text"]), "license": rec.get("license"),
    }


# ------------------------------------------------------------------------ driver

def run():
    CLEAN.mkdir(parents=True, exist_ok=True)
    for src, fn in (("fandom", clean_fandom), ("liquipedia", clean_liquipedia), ("blizzard", clean_blizzard)):
        raw = RAW / src / "pages.jsonl"
        if not raw.exists():
            continue
        kept = dropped = 0
        with open(raw, encoding="utf-8") as f, \
                open(CLEAN / f"{src}.jsonl", "w", encoding="utf-8") as out:
            for line in f:
                rec = fn(json.loads(line))
                if len(rec["text"].split()) < MIN_WORDS:
                    dropped += 1
                    continue
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                kept += 1
        print(f"{src}: {kept} pages gardees, {dropped} ecartees (< {MIN_WORDS} mots)")
