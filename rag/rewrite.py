"""Normalisation de la question avant recherche et reponse (saisies de joueurs : fautes, ellipses, mots-cles).

fix_entities(q)      : correction deterministe des noms d'entites mal orthographies (rapidfuzz, sans LLM)
rewrite_question(q)  : reformulation en une question complete par le LLM qui repond (Ollama, temperature 0)
normalize(q, model)  : les deux a la suite, avec cache disque append-only (data/rag/rewrite_cache.jsonl) ;
                       mode="auto" : reformulation seulement si la saisie n'est pas deja une question (needs_rewrite)
"""
import json
import re
import time

import requests

from rag import common as C

OLLAMA = C.OLLAMA
CACHE = C.RAG_DIR / "rewrite_cache.jsonl"

MIN_LEN = 4          # longueur minimale d'un mot candidat a la correction
MIN_SCORE = 85       # fuzz.ratio minimal (formes normalisees) pour remplacer un nom a majuscule (a 80 : Kyung -> Myung, Maiko -> Mario)
MIN_SCORE_LOWER = 80 # seuil pour un mot tout en minuscules : un auteur soigneux met la majuscule aux noms propres
KEEP_WORDS = 0.8     # part minimale des mots de contenu de la question gardes par la reformulation (sinon rejetee)
KNOWN_DF = 20        # un mot present dans >= KNOWN_DF chunks du corpus est un vrai mot, pas une faute

# mots courants et mots du domaine jamais corriges (en plus du garde par frequence dans le corpus)
STOP = set("""
what which who whom whose when where why how does did doing done have has had having this that these those there
their them they then than from with without about into onto over under after before during while since until
hero heroes heal heals healing health cooldown cooldowns season seasons ultimate ultimates ability abilities perk
perks patch patches nerf nerfed buff buffed damage tank tanks support supports role roles map maps mode modes
team teams player players game games skin skins lore story voice real name names age born country nationality
weapon weapons ammo armor shield shields speed range duration cost charge charges passive talent talents
winner winners champion champions match matches final finals world cup open esport esports league
are was were been being will would could should might must can cannot your yours mine
the and for its out not but all any per
""".split())


def _proper_name_part(words, i):
    """Mot pris dans un nom propre de plusieurs mots absent des entites (« Zehra Sarioglu », « Boris Rehlinger ») :
    voisin a majuscule. Une faute de joueur porte sur un nom isole (« Gesnji ultimate »)."""
    def cap(j):
        return 0 <= j < len(words) and words[j][2][:1].isupper() and words[j][2].lower() not in STOP
    return words[i][2][:1].isupper() and (cap(i - 1) or cap(i + 1))


def _inflection(a, b):
    """« Samoan » / « Samoa », « Genjis » / « Genji » : derive du meme nom, pas une faute."""
    return a.startswith(b) or b.startswith(a)

_ent = {}


def _norm(s):
    from rag.retrieve import _norm as n
    return n(s).strip()


def _entity_titles():
    """{forme normalisee: titre d'affichage} des pages d'entites (heros, personnages, lieux, cartes)."""
    if "t" not in _ent:
        from rag.retrieve import _entities, get_index
        ix = get_index()
        _ent["t"] = {t.strip(): ix.docs[i]["title"] for t, i in _entities(ix).items()}
        _ent["ix"] = ix
    return _ent["t"]


def _known_word(w):
    if w in STOP:
        return True
    p = _ent["ix"].bm25.post.get(w)
    return p is not None and len(p[0]) >= KNOWN_DF


def fix_entities(question, min_score=MIN_SCORE, min_score_lower=MIN_SCORE_LOWER):
    """Corrige les noms d'entites mal ecrits (bigrammes puis mots). Renvoie (question, [(avant, apres, score)])."""
    from rapidfuzz import fuzz, process
    titles = _entity_titles()
    single = [t for t in titles if " " not in t]
    double = [t for t in titles if t.count(" ") == 1]
    words = [(m.start(), m.end(), m.group()) for m in re.finditer(r"[A-Za-z0-9À-ſ]+", question)]
    edits, i = [], 0
    while i < len(words):
        if i + 1 < len(words):
            a, b = words[i], words[i + 1]
            na, nb = _norm(a[2]), _norm(b[2])
            raw = na + " " + nb
            if question[a[1]:b[0]].strip() == "" and len(raw) >= 2 * MIN_LEN and raw not in titles \
                    and na not in STOP and nb not in STOP and not (_known_word(na) and _known_word(nb)):
                r = process.extractOne(raw, double, scorer=fuzz.ratio)
                if r and r[1] >= min_score:
                    edits.append((a[0], b[1], a[2] + " " + b[2], titles[r[0]], r[1]))
                    i += 2
                    continue
        s, e, w = words[i]
        n = _norm(w)
        if len(n) >= MIN_LEN and n not in titles and not _known_word(n) and not _proper_name_part(words, i):
            r = process.extractOne(n, single, scorer=fuzz.ratio)
            # mot en minuscules ou en tete de saisie (« Zaria graviton... ») : seuil plus bas
            thr = min_score_lower if w.islower() or i == 0 else min_score
            if r and r[1] >= thr and not _inflection(n, r[0]):
                edits.append((s, e, w, titles[r[0]], r[1]))
        i += 1
    out = question
    for s, e, _, new, _ in reversed(edits):
        out = out[:s] + new + out[e:]
    return out, [(w, new, round(sc)) for _, _, w, new, sc in edits]


# ------------------------------------------------------------------ reformulation par LLM

SYSTEM = ("Rewrite the user's message as ONE complete, correctly spelled English question about the video game "
          "Overwatch. Keep every name, number and condition. Do not answer it, do not add information. "
          "Reply with the question only.")
SHOTS = [
    ("Zaria graviton surge duration", "What is the duration of Zarya's Graviton Surge ultimate?"),
    ("lucio hp", "How much health does Lucio have?"),
    ("who voices Winston??", "Who is the voice actor of Winston in Overwatch?"),
    ("Ilios added when", "When was the map Ilios added to Overwatch?"),
    ("What is the cooldown of Mercy's Resurrect?", "What is the cooldown of Mercy's Resurrect?"),
]


_Q = r"(?:What|Which|Who|When|Where|How|Why|If|After|Before|Can|Is|Does|Do|For|On|In|During)"
_DOUBLE = re.compile(rf"^({_Q})\s+({_Q})\b")
_QWORD = re.compile(r"^(what|which|who|whom|whose|when|where|why|how|is|are|was|were|does|do|did|can|could|has|have|"
                    r"had|will|would|should|in|on|during|after|before|for|at|by|if|since|from|between|according|"
                    r"under|as|to|among|with|apart|besides|other|name|list|i'm|i)\b", re.I)


def rewrite_question(question, model, ollama_url=OLLAMA, timeout=120):
    """Renvoie (question reformulee, ok). Repli sur l'entree (ok=False si erreur reseau)."""
    # exemples dans un seul message utilisateur : les modeles fine-tunes (RAFT) derivent en conversation multi-tours
    shots = "\n\n".join(f"Message: {u}\nQuestion: {a}" for u, a in SHOTS)
    user = f"Examples:\n\n{shots}\n\nNow the real message.\n\nMessage: {question}\nQuestion:"
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    body = {"model": model, "messages": msgs, "stream": False, "think": False, "keep_alive": "30m",
            "options": {"temperature": 0, "num_predict": 64, "num_ctx": 8192}}
    try:
        r = requests.post(f"{ollama_url}/api/chat", json=body, timeout=timeout)
        r.raise_for_status()
        text = r.json().get("message", {}).get("content", "")
    except (requests.RequestException, ValueError):
        return question, False
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return question, True
    text = re.sub(r"^(question|rewritten( question)?|rewrite)\s*:\s*", "", lines[0], flags=re.I).strip(" \"'`")
    # le SLM fine-tune (RAFT) repete parfois le 1er mot (« What What is ... », « Which What heroes ... »)
    text = _DOUBLE.sub(r"\2", text)
    if not text or len(text.split()) > 3 * len(question.split()) + 20 or not _keeps_content(question, text):
        return question, True
    return text, True


def _content_words(s):
    return {w for w in _norm(s).split() if len(w) >= 3 and w not in STOP}


def _keeps_content(question, text):
    """Rejette une reformulation qui perd les mots de contenu de la question : le RAFT repond parfois au lieu de
    reformuler (« None of the provided answers match... ») ou remplace un nom (« Which Ilios was added... »)."""
    src = _content_words(question)
    return not src or len(src & _content_words(text)) >= KEEP_WORDS * len(src)


def needs_rewrite(question):
    """Mode « auto » : seules les saisies qui ne sont pas deja une question complete sont reformulees (mots-cles,
    point d'interrogation absent). Sur le dev (questions redigees), reformuler fait perdre ~3 points : paraphrases
    qui changent la recherche (« How did the matches work out » -> « match outcomes »), « in Overwatch » ajoute."""
    q = question.strip()
    return not (q.endswith("?") and _QWORD.match(q) and len(q.split()) >= 4)


# ------------------------------------------------------------------ normalisation complete + cache

_cache = {}
_loaded = []


def _load_cache():
    if _loaded:
        return
    _loaded.append(True)
    if CACHE.exists():
        for ln in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(ln)
                # cle = texte reellement reformule (apres correction des entites) : un changement des regles de
                # fix_entities ne reutilise pas une reformulation faite sur un autre texte
                _cache[(d["model"], d["after_fix"])] = d
            except (ValueError, KeyError):
                pass


def normalize(question, model, ollama_url=OLLAMA, use_cache=True, mode="always"):
    """fix_entities puis rewrite_question. mode « always » : toujours reformuler ; « auto » : seulement si
    needs_rewrite (la correction des entites s'applique toujours, sans LLM). Renvoie (question_normalisee, details) ;
    details = {'fixed', 'after_fix', 'rewritten' (reformulation demandee), 'rewrite_s' (duree mesuree a l'origine
    si cache), 'cached'}."""
    _load_cache()
    t0 = time.time()
    fixed_q, fixed = fix_entities(question)
    if mode == "auto" and not needs_rewrite(fixed_q):
        return fixed_q, {"fixed": fixed, "after_fix": fixed_q, "rewritten": False, "rewrite_s": time.time() - t0,
                         "cached": False}
    key = (model, fixed_q)
    if use_cache and key in _cache:
        d = _cache[key]
        out = d["normalized"] if _keeps_content(fixed_q, d["normalized"]) else fixed_q   # garde ajoute apres coup
        return out, {"fixed": fixed, "after_fix": fixed_q, "rewritten": True, "rewrite_s": d["rewrite_s"], "cached": True}
    out, ok = rewrite_question(fixed_q, model, ollama_url)
    dt = time.time() - t0
    rec = {"model": model, "question": question, "after_fix": fixed_q, "fixed": fixed, "normalized": out,
           "rewrite_s": round(dt, 3)}
    if use_cache and ok:        # une erreur reseau n'est pas memorisee
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _cache[key] = rec
    return out, {"fixed": fixed, "after_fix": fixed_q, "rewritten": True, "rewrite_s": dt, "cached": False}
