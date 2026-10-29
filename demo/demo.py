"""Demo de soutenance : poser des questions au SLM, avec ou sans RAG, en affichant latence et memoire.
Meme prompt et meme recherche que le banc (bench.prompts + rag.retrieve, k = 4).
La question est normalisee par defaut (rag.rewrite : fautes de noms corrigees, question reformulee par le modele) ;
--no-rewrite ou /rewrite pour la desactiver.

Usage :
  python -m demo.demo                                  # interactif, RAFT 4B v2 + RAG
  python -m demo.demo --model ow-qwen3-1.7b-raft      # plus petit, plus rapide
  python -m demo.demo --ask "What is the ultimate ability of the hero Kestrel?" --compare

Commandes en mode interactif :
  /rag           active ou coupe le RAG          /compare   la prochaine question : sans RAG puis avec
  /rewrite       active ou coupe la normalisation de la question (fautes, question elliptique)
  /model NOM     change de modele Ollama         /sources   affiche ou masque les passages trouves
  /aide          rappelle les commandes          /quitter   (ou Ctrl+D)
"""
import argparse
import json
import sys
import time

import requests

from bench.prompts import build_messages

OLLAMA = "http://localhost:11434"
# 4B par defaut : le 1.7B confond les lignes 5v5 / 6v6 des notes de patch sur la question Roadhog (S04)
DEFAULT_MODEL = "ow-qwen3-4b-raft-v2"
K = 4
OPTIONS = {"temperature": 0, "num_ctx": 8192, "num_predict": 400}   # comme le banc

# Couleurs ANSI (terminal macOS / Linux ; ignorees si la sortie n'est pas un terminal)
_TTY = sys.stdout.isatty()


def c(text, code):
    return f"\033[{code}m{text}\033[0m" if _TTY else text


DIM, BOLD, ORANGE, BLUE, GREEN, RED = "2", "1", "33", "34", "32", "31"


def page_title(text):
    """Premiere ligne d'un passage : « Page: X Section: Y »."""
    line = text.strip().splitlines()[0] if text.strip() else ""
    return line.replace("Page: ", "")[:110]


def model_memory(model):
    try:
        for m in requests.get(f"{OLLAMA}/api/ps", timeout=5).json().get("models", []):
            if m.get("name") in (model, f"{model}:latest") or m.get("model") in (model, f"{model}:latest"):
                return m.get("size", 0) / 1e9
    except requests.RequestException:
        pass
    return None


def check_ollama(model):
    try:
        names = {m["name"] for m in requests.get(f"{OLLAMA}/api/tags", timeout=5).json().get("models", [])}
    except requests.RequestException:
        sys.exit("Ollama ne repond pas sur localhost:11434 : lancer l'application Ollama (ou `ollama serve`).")
    if model not in names and f"{model}:latest" not in names:
        sys.exit(f"Modele {model} absent d'Ollama. Voir docs/REPRISE_MAC.md (ollama create ...).")


def warm_up(model):
    """Charge le modele (et le modele d'embeddings) avant la premiere question : pas d'attente devant le jury."""
    print(c(f"Chargement de {model}...", DIM), end="", flush=True)
    t0 = time.time()
    # memes options que les questions (num_ctx surtout) : sinon Ollama recharge le modele a la 1re question
    requests.post(f"{OLLAMA}/api/chat", json={"model": model, "messages": [{"role": "user", "content": "Hi"}],
                                              "stream": False, "think": False, "keep_alive": "60m",
                                              "options": OPTIONS | {"num_predict": 1}}, timeout=600)
    from rag.retrieve import get_index, retrieve
    get_index()
    retrieve("warm-up", K)  # charge l'index et le modele d'embeddings
    print(c(f" pret ({time.time() - t0:.1f} s)", DIM))


def answer(question, model, use_rag, show_sources, rewrite=False):
    passages, t_rag, t_rw = None, 0.0, 0.0
    if rewrite:
        from rag.rewrite import normalize
        t0 = time.time()
        norm, _ = normalize(question, model, OLLAMA, mode="auto")
        t_rw = time.time() - t0
        if norm != question:
            print(c(f"  Question normalisee : {norm}", DIM))
        question = norm
    if use_rag:
        from rag.retrieve import retrieve
        t0 = time.time()
        passages = retrieve(question, K)
        t_rag = time.time() - t0
        if show_sources:
            print(c(f"  Passages trouves ({t_rag * 1000:.0f} ms) :", DIM))
            for i, p in enumerate(passages, 1):
                print(c(f"   [{i}] {page_title(p['text'])}", DIM))
    label = c("avec RAG", BLUE) if use_rag else c("sans RAG", ORANGE)
    print(f"{c(model, BOLD)} ({label}) > ", end="", flush=True)
    body = {"model": model, "messages": build_messages(question, passages), "stream": True, "think": False,
            "keep_alive": "60m", "options": OPTIONS}
    t0 = time.time()
    ttft, final = None, {}
    with requests.post(f"{OLLAMA}/api/chat", json=body, stream=True, timeout=600) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            d = json.loads(line)
            piece = d.get("message", {}).get("content", "")
            if piece:
                if ttft is None:
                    ttft = time.time() - t0
                print(piece, end="", flush=True)
            if d.get("done"):
                final = d
    total = time.time() - t0 + t_rag + t_rw
    tok_s = final.get("eval_count", 0) / (final.get("eval_duration", 1) / 1e9) if final.get("eval_duration") else 0
    mem = model_memory(model)
    stats = [f"{total:.2f} s au total", f"normalisation {t_rw:.2f} s" if rewrite else None,
             f"recherche {t_rag * 1000:.0f} ms" if use_rag else None,
             f"premier mot {ttft:.2f} s" if ttft else None, f"{tok_s:.0f} tokens/s" if tok_s else None,
             f"memoire du modele {mem:.1f} Go" if mem else None]
    print("\n" + c("  " + " | ".join(s for s in stats if s), GREEN) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Demo OW-SLM (SLM + RAG local)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-rag", action="store_true", help="demarrer sans RAG")
    ap.add_argument("--ask", help="poser une seule question puis quitter")
    ap.add_argument("--no-rewrite", action="store_true", help="ne pas normaliser la question avant la recherche")
    ap.add_argument("--compare", action="store_true", help="avec --ask : sans RAG puis avec RAG")
    a = ap.parse_args()
    model, use_rag, show_sources, compare_next = a.model, not a.no_rag, True, False
    rewrite = not a.no_rewrite
    check_ollama(model)
    warm_up(model)
    if a.ask:
        if a.compare:
            answer(a.ask, model, False, show_sources, rewrite)
        answer(a.ask, model, True if a.compare else use_rag, show_sources, rewrite)
        return
    print(c("OW-SLM : un petit modele specialise Overwatch, 100 % local. /aide pour les commandes.\n", BOLD))
    while True:
        try:
            q = input(c("Question > ", BOLD)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.startswith("/"):
            cmd, _, arg = q.partition(" ")
            if cmd in ("/quitter", "/quit", "/q"):
                break
            elif cmd == "/rag":
                use_rag = not use_rag
                print(c(f"RAG {'active' if use_rag else 'coupe'}", DIM))
            elif cmd == "/rewrite":
                rewrite = not rewrite
                print(c(f"Normalisation de la question {'activee' if rewrite else 'coupee'}", DIM))
            elif cmd == "/compare":
                compare_next = True
                print(c("La prochaine question sera posee sans RAG, puis avec RAG.", DIM))
            elif cmd == "/sources":
                show_sources = not show_sources
                print(c(f"Passages {'affiches' if show_sources else 'masques'}", DIM))
            elif cmd == "/model" and arg:
                check_ollama(arg.strip())
                model = arg.strip()
                warm_up(model)
            else:
                print(__doc__.split("Commandes en mode interactif :")[1])
            continue
        try:
            if compare_next:
                answer(q, model, False, show_sources, rewrite)
                answer(q, model, True, show_sources, rewrite)
                compare_next = False
            else:
                answer(q, model, use_rag, show_sources, rewrite)
        except requests.RequestException as e:
            print(c(f"\nErreur Ollama : {e}", RED))


if __name__ == "__main__":
    main()
