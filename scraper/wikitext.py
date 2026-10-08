import re

import mwparserfromhell as mwp

DROP_LINK_PREFIX = ("file:", "image:", "category:", "media:")

H = "§H"   # marqueur provisoire de titre
LI = "§L§"  # marqueur provisoire d'item de liste


def _norm(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def _strip_value(code_str):
    code = mwp.parse(code_str)
    for t in code.filter_templates(recursive=False):
        try:
            code.remove(t)
        except ValueError:
            pass
    return _norm(code.strip_code(normalize=True, collapse=True))


NAME_TEMPLATES = {"hero", "heroicon", "hero icon", "team", "teamshort", "player", "ability",
                  "opponent", "ver"}


def _inline_name_templates(code):
    """Remplace {{Hero|D.Mon}} etc. par leur 1er parametre positionnel."""
    for t in code.filter_templates(recursive=True):
        if str(t.name).strip().lower() not in NAME_TEMPLATES:
            continue
        val = None
        for p in t.params:
            if p.showkey:
                continue
            val = _norm(str(p.value))
            break
        if val is None:
            continue
        try:
            code.replace(t, val)
        except ValueError:
            pass


def _infobox_text(tpl):
    name = str(tpl.name).strip()
    lines = [f"Infobox: {_norm(name[len('infobox'):]) or name}"]
    for p in tpl.params:
        key = _norm(str(p.name))
        if not key or key.isdigit():
            continue
        val = _strip_value(re.sub(r"<br\s*/?>", "; ", str(p.value)))
        if val:
            lines.append(f"{key.replace('_', ' ')}: {val}")
    return "\n".join(lines)


def clean_wikitext(wt, tidy):
    """wikitext -> texte. `tidy` : fonction de normalisation finale."""
    # strip_code supprimerait les marqueurs de titres/listes : on les protege.
    wt = re.sub(r"^(={2,6})[ \t]*(.*?)[ \t]*\1[ \t]*$",
                lambda m: f"\n{H}{len(m.group(1))}§ {m.group(2)}\n", wt, flags=re.M)
    wt = re.sub(r"^([*#]+)[ \t]*", lambda m: "  " * (len(m.group(1)) - 1) + LI + " ", wt, flags=re.M)
    code = mwp.parse(wt)
    _inline_name_templates(code)
    infoboxes = []
    for t in code.filter_templates(recursive=False):
        if str(t.name).strip().lower().startswith("infobox"):
            infoboxes.append(_infobox_text(t))
        try:
            code.remove(t)
        except ValueError:
            pass
    for link in code.filter_wikilinks():
        if str(link.title).strip().lower().startswith(DROP_LINK_PREFIX):
            try:
                code.remove(link)
            except ValueError:
                pass
    text = code.strip_code(normalize=True, collapse=False)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"__[A-Z]+__", "", text)
    text = re.sub(r"^[;:]+[ \t]*", "", text, flags=re.M)
    text = re.sub(r"^\{\|.*|^\|[-+}].*|^!.*", "", text, flags=re.M)  # residus de tableaux wiki
    text = re.sub(re.escape(H) + r"(\d)§ ?",
                  lambda m: "\n" + "#" * min(int(m.group(1)), 6) + " ", text)
    text = text.replace(LI, "-")
    body = tidy(text)
    return tidy("\n".join(infoboxes) + "\n\n" + body) if infoboxes else body
