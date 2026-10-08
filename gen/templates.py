"""Q/R deterministes (sans LLM) depuis les infobox (lignes `Cle: valeur`) et les templates AwardPrizePool.

Lecture seule de data/clean, data/chunks et data/raw ; ecrit uniquement data/qa/templates.jsonl.
Les questions inverses (« Which hero's real name is X ? ») ne sont emises que si la valeur est unique
dans tout le corpus pour cette cle (sinon la reponse serait ambigue).
Les vainqueurs de tournois ne sont PAS generes (brackets non fiables).
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import mwparserfromhell as mwp

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
CHUNKS = ROOT / "data" / "chunks" / "chunks.jsonl"
RAW_LIQUI = ROOT / "data" / "raw" / "liquipedia" / "pages.jsonl"
OUT = ROOT / "data" / "qa" / "templates.jsonl"

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]

# pages Fandom dont l'infobox n'est pas un « personnage / lieu » exploitable
FANDOM_SKIP_CATS = {"voice actors", "international dubs", "patches", "quotations", "transcripts",
                    "comics", "hero cosmetics pages", "event cosmetics pages", "cosmetics"}


CHAR_CAT = re.compile(r"character|members|omnic|cyborg|talon|junker|foes|outlaws|gladiators", re.I)

# ------------------------------------------------------------------ utilitaires

def fmt_date(s):
    """'2017-12-06' -> 'December 6, 2017' ; '2016-06' -> 'June 2016' ; sinon None."""
    s = (s or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        if 1 <= mo <= 12 and 1 <= d <= 31 and y > 1900:
            return f"{MONTHS[mo - 1]} {d}, {y}"
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if m and 1 <= int(m[2]) <= 12 and int(m[1]) > 1900:
        return f"{MONTHS[int(m[2]) - 1]} {m[1]}"
    return None


def fmt_range(s, e):
    ds, de = fmt_date(s), fmt_date(e)
    if ds and de:
        return f"on {ds}" if ds == de else f"from {ds} to {de}"
    return None


def clean_val(v):
    """Retire les parentheses en alphabet non latin et les marqueurs de lien."""
    v = re.sub(r"\([^()]*[^\x00-\x7fÀ-ɏ][^()]*\)", "", v)
    v = v.replace("Link▶️", "").replace("▶️", "")
    return re.sub(r"\s+", " ", v).strip(" ;,")


def parse_infobox_lines(block):
    """[(cle_minuscule, valeur)] d'un bloc `Cle: valeur` ; ignore les lignes [Section]."""
    out = []
    for ln in block.split("\n"):
        m = re.match(r"^([A-Za-z][A-Za-z0-9 _\-']{0,40}?): (.+)$", ln)
        if m:
            out.append((m.group(1).strip().lower(), m.group(2).strip()))
    return out


def first_wins(pairs):
    d = {}
    for k, v in pairs:
        d.setdefault(k, v)
    return d


def art(w):
    return "an" if w[:1].lower() in "aeiou" else "a"


def sentence(s):
    return s if s.endswith((".", "!", "?")) else s + "."


# ------------------------------------------------------------------ collecteur

class Collector:
    def __init__(self, chunks):
        self.chunks = chunks            # (source, pageid) -> [(id, revid, text)]
        self.pairs = []                 # paires emises
        self.rev = defaultdict(list)    # (tag, valeur_norm) -> [index de paire inverse]
        self.n = Counter()

    def chunk_of(self, source, pageid, needle=None):
        lst = self.chunks.get((source, pageid), [])
        if not lst:
            return None, None
        if needle:
            for cid, rv, txt in lst:
                if needle in txt:
                    return cid, rv
        return lst[0][0], lst[0][1]

    def add(self, rec, qs, a, category, sensitive=False, volatile=False, needle=None, reverse=None):
        """qs : formulations de la question ; a : reponse commune. reverse = (tag, valeur, question, reponse)."""
        cid, rv = self.chunk_of(rec["source"], rec["pageid"], needle)
        seen_q = set()
        for q in qs:
            if q in seen_q:
                continue
            seen_q.add(q)
            self._push(rec, q, a, category, sensitive, volatile, cid, rv)
        if reverse:
            tag, val, q, ra = reverse
            self.rev[(tag, val.strip().lower())].append(
                (rec, q, ra, category, sensitive, volatile, cid, rv))

    def _push(self, rec, q, a, category, sensitive, volatile, cid, rv):
        key = (rec["source"], rec["pageid"], q)
        if key in self.n:
            return
        self.n[key] = 1
        self.pairs.append({
            "id": f"tpl:{rec['source']}:{rec['pageid']}:{len(self.pairs)}",
            "source": rec["source"], "title": rec["title"], "chunk_id": cid,
            "revid": rv if cid else rec.get("revid"), "kind": "template", "category": category,
            "sensitive": sensitive, "volatile": volatile, "question": q, "answer": a})

    def flush_reverse(self):
        kept = 0
        for (_, _), lst in self.rev.items():
            if len({x[0]["pageid"] for x in lst}) != 1:
                continue  # valeur partagee par plusieurs entites : ambigu
            rec, q, ra, cat, sens, vol, cid, rv = lst[0]
            self._push(rec, q, ra, cat, sens, vol, cid, rv)
            kept += 1
        return kept


# ------------------------------------------------------------------ Fandom

ABILITY_STATS = {
    "cooldown": "cooldown", "damage": "damage", "healing": "healing", "ammo": "ammunition",
    "reload time": "reload time", "duration": "duration", "rate of fire": "rate of fire",
    "cast time": "cast time", "projectile speed": "projectile speed", "range": "range",
    "ultimate cost": "ultimate cost", "max health": "maximum health", "radius": "radius",
    "barrier health": "barrier health", "movement speed": "movement speed",
}


def fandom_hero(col, rec, info, text):
    t = rec["title"]
    is_hero = "heroes" in {c.lower() for c in rec["categories"]}
    who = "hero" if is_hero else "character"
    S = lambda *a, **k: col.add(rec, *a, **k)

    rn = clean_val(info.get("real name", ""))
    if re.search(r"[Ѐ-鿿가-힯]", rn) or rn.lower() == t.lower():
        rn = ""
    if rn:
        a = f"{t}'s real name is {rn}."
        S([f"What is {t}'s real name?", f"What is the real name of the Overwatch {who} {t}?",
           f"What is the full civilian name of {t} in Overwatch?"], a, "hero",
          reverse=(f"realname:{who}", rn, f"Which Overwatch {who}'s real name is {rn}?",
                   f"{rn} is the real name of {t}."))
    nat = clean_val(info.get("nationality", ""))
    if nat:
        S([f"What is {t}'s nationality in Overwatch?", f"What nationality is the Overwatch {who} {t}?"],
          f"{t}'s nationality is {nat}.", "hero")
    birth = clean_val(info.get("birth", ""))
    if birth:
        S([f"When was {t} born in the Overwatch lore?", f"What is {t}'s birth date in Overwatch?"],
          f"{t}'s birth date is {birth}.", "hero")
    age = clean_val(info.get("age", ""))
    if age:
        S([f"How old is {t} in Overwatch?", f"What is the age of the Overwatch {who} {t}?"],
          f"{t}'s age is listed as {age}.", "hero")
    occ = clean_val(info.get("occupation", ""))
    if occ:
        S([f"What is {t}'s occupation in Overwatch?", f"What is the occupation of the Overwatch {who} {t}?"],
          f"{t}'s occupation is {occ}.", "hero")
    base = clean_val(info.get("base", ""))
    if base:
        S([f"Where is {t}'s base of operations?", f"Where is the Overwatch {who} {t} based?"],
          f"{t}'s base of operations is {base}.", "hero")
    aff = clean_val(info.get("affiliation", ""))
    if aff:
        S([f"What is {t}'s affiliation in Overwatch?", f"Which organizations is {t} affiliated with in Overwatch?"],
          f"{t}'s affiliation is {aff}.", "hero")
    if is_hero:
        role, sub = clean_val(info.get("role", "")), clean_val(info.get("sub-role", ""))
        if role:
            a = f"{t} is a {role} hero" + (f" with the {sub} sub-role." if sub else ".")
            S([f"What is {t}'s role in Overwatch?", f"Which role does the hero {t} belong to in Overwatch?"]
              + ([f"What is {t}'s role and sub-role?"] if sub else []), a, "hero")
        if sub:
            S([f"What is {t}'s sub-role in Overwatch?", f"Which sub-role does {t} have?"],
              f"{t}'s sub-role is {sub}.", "hero")
        stats = [(k, clean_val(info.get(k, ""))) for k in ("health", "armor", "shields")]
        stats = [(k, v) for k, v in stats if re.match(r"^\d", v)]
        for k, v in stats:
            S([f"How much {k} does {t} have?", f"What is {t}'s base {k} in Overwatch?"],
              f"{t} has {v} {k}.", "hero_stats", sensitive=True)
        if len(stats) >= 2:
            lst = ", ".join(f"{v} {k}" for k, v in stats)
            S([f"What are {t}'s base health, armor and shields?",
               f"What are the base defensive stats of {t} in Overwatch?"],
              f"{t} has {lst}.", "hero_stats", sensitive=True)
        m = re.search(r"Released on (\d{1,2} \w+ \d{4}|\w+ \d{1,2}, \d{4})(?:[,.][^.]*?(\d+(?:st|nd|rd|th)) hero)?", text)
        if m:
            a = f"{t} was released on {m.group(1)}."
            S([f"When was {t} released in Overwatch?", f"On what date was the hero {t} released?"], a, "hero")
            if m.group(2):
                S([f"Which number hero added to the game was {t}?"],
                  f"{t} was the {m.group(2)} hero added to Overwatch, released on {m.group(1)}.", "hero")
        # capacites
        i = text.find("\n## Abilities")
        if i >= 0:
            j = text.find("\n## ", i + 5)
            sec = text[i:j if j > 0 else None]
            for blk in re.split(r"\n#### ", sec)[1:]:
                name, _, body = blk.partition("\n")
                name = name.strip()
                if not name or name.lower().startswith("sub-role") or len(name) > 60:
                    continue
                f = first_wins(parse_infobox_lines(body.split("\nAdditional details")[0]))
                key = f.get("key", "").strip("[] ")
                if key and len(key) <= 30:
                    S([f"Which key activates {t}'s {name}?", f"What is the keybind of {t}'s {name} ability?"],
                      f"{t}'s {name} is activated with {key}.", "ability", needle=f"#### {name}")
                if "ultimate" in f.get("type", "").lower():
                    S([f"What is {t}'s ultimate ability?", f"Which ultimate does {t} have in Overwatch?"],
                      f"{t}'s ultimate ability is {name}.", "ability", needle=f"#### {name}",
                      reverse=(f"ultimate", name, f"Which hero has the ultimate ability {name}?",
                               f"{name} is {t}'s ultimate ability."))
                for k, label in ABILITY_STATS.items():
                    v = f.get(k, "")
                    if v and re.match(r"^\d", v) and len(v) <= 80:
                        S([f"What is the {label} of {t}'s {name}?",
                           f"What {label} value is listed for {t}'s {name} ability?"],
                          f"The {label} of {t}'s {name} is {v}.", "ability_stats", sensitive=True,
                          needle=f"#### {name}")


def fandom_map(col, rec, info):
    t = rec["title"]
    S = lambda *a, **k: col.add(rec, *a, **k)
    ty = clean_val(info.get("type", ""))
    if ty and len(ty) < 40:
        S([f"What type of map is {t} in Overwatch?", f"Which game mode type does the map {t} belong to?"],
          f"{t} is {art(ty)} {ty} map.", "map")
    loc = clean_val(info.get("location", ""))
    if loc:
        S([f"Where is the Overwatch map {t} located?", f"In which place is the map {t} set?"],
          f"{t} is located in {loc}.", "map")
    rd = fmt_date(info.get("release date", ""))
    if rd:
        S([f"When was the map {t} released in Overwatch?", f"On what date did {t} become available?"],
          f"{t} was released on {rd}.", "map")
    modes = clean_val(info.get("available modes", ""))
    if modes:
        S([f"Which modes are available on the map {t}?", f"In which game modes can you play on {t}?"],
          f"The available modes on {t} are: {modes}.", "map")


# ------------------------------------------------------------------ Liquipedia

def liqui_player(col, rec, info):
    t = rec["title"]
    pid = clean_val(info.get("id", "")) or t
    p = t if re.search(r"\(.*\)$", t) else pid  # titre desambiguise si besoin
    S = lambda *a, **k: col.add(rec, *a, **k)
    rom, nat_name = clean_val(info.get("romanized name", "")), clean_val(info.get("name", ""))
    real = rom or (nat_name if nat_name.isascii() else "")
    if real:
        extra = f" (native name: {nat_name})" if rom and nat_name and nat_name != rom else ""
        S([f"What is the real name of the Overwatch player {p}?", f"What is the full name of the esports player {p}?"],
          f"{p}'s name is {real}{extra}.", "player",
          reverse=("player_name", real, f"Which Overwatch esports player's real name is {real}?",
                   f"{real} is the real name of the player {p}."))
    c = clean_val(info.get("country", ""))
    if c:
        S([f"Which country is the Overwatch player {p} from?", f"What is {p}'s nationality on Liquipedia?"],
          f"{p} is from {c}.", "player")
    r = clean_val(info.get("roles", ""))
    if r:
        S([f"What role does {p} play in Overwatch esports?", f"Which role is the Overwatch player {p} known for?"],
          f"{p} plays the {r} role.", "player")
    tm = clean_val(info.get("team", ""))
    if tm:
        S([f"Which team is the Overwatch player {p} listed with on Liquipedia?", f"Which team does {p} play for?"],
          f"On Liquipedia, {p} is listed with the team {tm}.", "player", volatile=True)
    st = clean_val(info.get("status", ""))
    if st:
        S([f"What is the current status of the Overwatch player {p} on Liquipedia?"],
          f"{p}'s status is listed as {st}.", "player", volatile=True)
    bd = fmt_date(info.get("birth date", ""))
    if bd:
        S([f"When was the Overwatch player {p} born?", f"What is {p}'s date of birth?"],
          f"{p} was born on {bd}.", "player")


def liqui_team(col, rec, info):
    t = rec["title"]
    n = clean_val(info.get("name", "")) or t
    S = lambda *a, **k: col.add(rec, *a, **k)
    loc = clean_val(info.get("location", ""))
    if loc:
        S([f"Where is the Overwatch team {n} based?", f"In which country or region is the esports team {n} located?"],
          f"The team {n} is located in {loc}.", "team")
    cr = fmt_date(info.get("created", ""))
    if cr:
        S([f"When was the Overwatch team {n} founded?", f"When was the esports team {n} created?"],
          f"{n} was created in {cr}." if len(info.get("created", "")) == 7 else f"{n} was created on {cr}.", "team")
    ds = fmt_date(info.get("disbanded", ""))
    if ds:
        S([f"When did the Overwatch team {n} disband?", f"On what date was the esports team {n} disbanded?"],
          f"{n} disbanded on {ds}." if len(info.get("disbanded", "")) > 7 else f"{n} disbanded in {ds}.", "team")


def liqui_league(col, rec, info):
    n = clean_val(info.get("name", "")) or rec["title"]
    S = lambda *a, **k: col.add(rec, *a, **k)
    rng = fmt_range(info.get("sdate", ""), info.get("edate", ""))
    if rng:
        S([f"When did {n} take place?", f"What were the start and end dates of {n}?"],
          f"{n} took place {rng}.", "tournament")
    ty = info.get("type", "").strip().lower()
    cities = list(dict.fromkeys(clean_val(v) for k, v in info.items() if re.fullmatch(r"city\d*", k) and v))
    countries = list(dict.fromkeys(clean_val(v) for k, v in info.items() if re.fullmatch(r"country\d*", k) and v))
    if ty == "online":
        S([f"Was {n} played online or offline?"], f"{n} was an online tournament.", "tournament")
    elif cities or countries:
        loc = " and ".join(cities) + (", " if cities and countries else "") + " / ".join(countries)
        S([f"Where was {n} held?", f"In which location did {n} take place?"],
          f"{n} was held in {loc}.", "tournament")
    venues = list(dict.fromkeys(clean_val(v) for k, v in info.items() if re.fullmatch(r"venue\d*", k) and v))
    if venues:
        S([f"Which venue hosted {n}?", f"At which arena or venue was {n} played?"],
          f"{n} was hosted at {' and '.join(venues)}.", "tournament")
    pp = info.get("prizepoolusd", "").strip()
    if re.fullmatch(r"\d[\d,]*(\.\d+)?", pp) and float(pp.replace(",", "")) > 0:
        S([f"What was the total prize pool of {n}?", f"How much prize money was at stake in {n}?"],
          f"The prize pool of {n} was ${pp} USD.", "tournament")
    tn = info.get("team number", "").strip()
    if tn.isdigit():
        S([f"How many teams took part in {n}?", f"What was the number of participating teams in {n}?"],
          f"{tn} teams took part in {n}.", "tournament")
    org = clean_val(info.get("organizer", ""))
    if org:
        S([f"Who organized {n}?", f"Which organization ran the tournament {n}?"],
          f"{n} was organized by {org}.", "tournament")
    tier = info.get("liquipediatier", "").strip()
    if tier.isdigit():
        S([f"What Liquipedia tier is {n}?"], f"{n} is a tier {tier} tournament on Liquipedia.", "tournament")


# ------------------------------------------------------------------ AwardPrizePool (MVP...)

def _extract_templates(wt, name):
    """Sous-chaines {{name ...}} avec appariement des accolades."""
    out, pos = [], 0
    while True:
        i = wt.find("{{" + name, pos)
        if i < 0:
            return out
        depth, j = 0, i
        while j < len(wt) - 1:
            two = wt[j:j + 2]
            if two == "{{":
                depth += 1
                j += 2
            elif two == "}}":
                depth -= 1
                j += 2
                if depth == 0:
                    break
            else:
                j += 1
        out.append(wt[i:j])
        pos = max(j, i + 2)


def _recipients(slot):
    res = []
    body = mwp.parse("\n".join(str(p.value) for p in slot.params if str(p.name).strip() != "award"))
    for t in body.filter_templates(recursive=True):
        if str(t.name).strip().lower().endswith("opponent"):
            name = None
            for p in t.params:
                if not p.showkey:
                    name = clean_val(str(p.value))
                    break
            team = clean_val(str(t.get("team").value)) if t.has("team") else ""
            if name:
                res.append((name, team))
    return res


def awards_from_raw(col, chunks_by_src):
    n_pages = 0
    if not RAW_LIQUI.exists():
        return
    with open(RAW_LIQUI, encoding="utf-8") as f:
        for line in f:
            if "AwardPrizePool" not in line:
                continue
            r = json.loads(line)
            wt = r["wikitext"]
            m = re.search(r"\{\{Infobox league.*?\|\s*name\s*=\s*([^\n|]+)", wt, re.S | re.I)
            n = clean_val(re.sub(r"<[^>]+>|\[\[|\]\]", "", m.group(1))) if m else r["title"]
            rec = {"source": "liquipedia", "pageid": r["pageid"], "title": r["title"], "revid": r.get("revid")}
            got = False
            for sub in _extract_templates(wt, "AwardPrizePool"):
                code = mwp.parse(sub)
                for slot in code.filter_templates(recursive=True):
                    if str(slot.name).strip().lower() != "slot" or not slot.has("award"):
                        continue
                    award = clean_val(str(slot.get("award").value))
                    rcp = _recipients(slot)
                    if not award or len(award) > 40 or not (1 <= len(rcp) <= 5) or award.lower().startswith("prize"):
                        continue
                    who = " and ".join(f"{a} ({b})" if b else a for a, b in rcp)
                    mvp = "mvp" in award.lower()
                    qs = ([f"Who was the {award} of {n}?", f"Who won the {award} award at {n}?"] if mvp
                          else [f"Who received the {award} award at {n}?",
                                f"Which player or team won the {award} award at {n}?"])
                    col.add(rec, qs, f"The {award} award at {n} went to {who}.", "award")
                    got = True
            n_pages += got
    print(f"AwardPrizePool: {n_pages} pages avec prix individuels")


# ------------------------------------------------------------------ pilote

def load_chunks():
    d = defaultdict(list)
    with open(CHUNKS, encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            src, pid, _ = c["id"].split(":")
            d[(src, int(pid))].append((c["id"], c["revid"], c["text"]))
    return d


def run():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    col = Collector(load_chunks())
    for src in ("fandom", "liquipedia"):
        p = CLEAN / f"{src}.jsonl"
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                text = rec["text"]
                head = text.split("\n\n")[0]
                if src == "fandom":
                    cats = {c.lower() for c in rec["categories"]}
                    if not head.startswith("Name: ") or cats & FANDOM_SKIP_CATS or rec["title"].endswith("Patch"):
                        continue
                    info = first_wins(parse_infobox_lines(head))
                    if "[Map]" in head or "maps" in cats:
                        fandom_map(col, rec, info)
                    elif "heroes" in cats or ("real name" in info and any(CHAR_CAT.search(c) for c in cats)):
                        fandom_hero(col, rec, info, text)
                else:
                    m = re.match(r"Infobox: (\w+)", head)
                    if not m:
                        continue
                    info = first_wins(parse_infobox_lines(head))
                    kind = m.group(1)
                    if kind == "player":
                        liqui_player(col, rec, info)
                    elif kind == "team":
                        liqui_team(col, rec, info)
                    elif kind == "league":
                        liqui_league(col, rec, info)
    awards_from_raw(col, None)
    n_rev = col.flush_reverse()
    with open(OUT, "w", encoding="utf-8") as out:
        for p in col.pairs:
            out.write(json.dumps(p, ensure_ascii=False) + "\n")
    cnt = Counter((p["source"], p["category"]) for p in col.pairs)
    for k, v in sorted(cnt.items()):
        print(f"{k[0]:11s} {k[1]:14s} {v}")
    print(f"total: {len(col.pairs)} paires (dont {n_rev} inverses uniques), "
          f"{sum(p['sensitive'] for p in col.pairs)} sensibles, "
          f"{sum(p['chunk_id'] is not None for p in col.pairs)} liees a un chunk -> {OUT}")
