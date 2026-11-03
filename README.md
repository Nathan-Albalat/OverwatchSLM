# OW-SLM — un petit modèle de langage spécialisé Overwatch

Projet d'UE (novembre 2026) — Nathan Albalat, Mathis Guilain.

**Question étudiée :** dans quels cas un SLM local (Qwen3 1.7B / 4B) est-il pertinent face à un LLM local (Qwen3 14B)
et aux modèles frontier (Claude Sonnet, Opus), sur un domaine de niche qui change à chaque patch ?

Overwatch sert de cas d'étude : assez niche pour que les modèles généralistes en sachent peu, assez documenté
(~3,9 M mots de wiki) pour construire un corpus, et mis à jour en continu (la Saison 5 est sortie pendant le projet,
le 6 octobre 2026).

## Résultats principaux

Jeu de test figé de 235 questions (lore, gameplay, patchs, esport, cartes, 16 questions sans réponse), noté par un
juge LLM vérifié à la main.

| Configuration | Score test |
|---|---|
| Qwen3 4B seul | 4,7 % |
| Qwen3 4B + SFT (102 k paires) | 11,5 % |
| Claude Sonnet seul | 43 % |
| **Qwen3 4B + RAG** (sans entraînement) | **86,6 – 87,9 %** |
| Qwen3 4B + RAFT (meilleure version, v4) | 85,3 % |
| Qwen3 14B + RAG | 90,6 % |
| Claude Sonnet + RAG | 93,8 % |

- **Le RAG fait l'essentiel du gain** (+78 à +82 points à toutes les tailles) et supprime presque toute l'hallucination (4B : 12 réponses inventées sur 16 questions sans réponse, puis 0).
- **Le fine-tuning seul n'apprend pas le domaine** : le modèle mémorise mal et invente des réponses avec aplomb.
- **Le RAFT** (fine-tuning au format RAG) ne bat pas le 4B de base malgré quatre versions ; il rend en revanche le
  1.7B plus fiable (1 hallucination sur 16 au lieu de 3).
- Sur **40 questions tapées par de vrais joueurs**, le 4B + RAG + normalisation de la question fait jeu égal avec
  Claude Sonnet + RAG (73,8 %).
- **Coût** : ~0,03 Wh par question en local, environ 5 000 fois moins cher que Claude Sonnet avec recherche web ;
  mise à jour après un patch en **6 secondes** (réindexation) contre plus de 3 h 30 de réentraînement pour un SFT.

Le dossier complet est dans [`docs/rendu_final.md`](docs/rendu_final.md), les tableaux du banc dans
[`eval/report/`](eval/report/).

## Architecture

```
scraper/   collecte (Fandom, Liquipedia, notes de patch Blizzard), nettoyage, découpe en chunks   -> CLI ow-scrape
gen/       génération de paires question/réponse (Qwen 35B local via Ollama) + templates, filtrage
rag/       index hybride BM25 + embeddings (fusion RRF), exemples RAFT, normalisation de la question -> CLI ow-rag
train/     fine-tuning QLoRA (Unsloth + TRL, sous WSL) : SFT, CPT, RAFT ; export GGUF pour Ollama
bench/     banc d'évaluation : runs reprenables, juge LLM, rapports                                -> CLI ow-bench
demo/      démo de soutenance (SLM + RAG en local, latence et mémoire affichées)
eval/      jeux de questions (test figé, dev, joueurs), jugements et rapports
docs/      dossier final et guide d'installation sur Mac
```

Le pipeline : scraping → 14 208 chunks → 107 271 paires Q/R filtrées (25,7 h de GPU, sans API payante) →
index RAG, données SFT/CPT et 15 000 exemples RAFT → entraînements QLoRA → banc sur 19 configurations.

## Lancer la démo

Prérequis : [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com), l'index RAG dans `data/rag/`
(non versionné, voir [`docs/REPRISE_MAC.md`](docs/REPRISE_MAC.md) pour le récupérer ou le reconstruire).

```
uv sync
ollama pull qwen3-embedding:0.6b
ollama pull hf.co/unsloth/Qwen3-4B-GGUF:Q4_K_M
uv run python -m demo.demo                                   # mode interactif, 4B + RAG
uv run python -m demo.demo --ask "What is Chopper's grapple cooldown?" --compare   # sans puis avec RAG
```

## Reproduire le pipeline

```
uv run ow-scrape fandom | liquipedia | blizzard --month 2026/10     # collecte (reprenable)
uv run ow-scrape clean && uv run ow-scrape chunk
uv run ow-scrape generate                                         # paires Q/R via Ollama (long, reprenable)
uv run ow-scrape templates && uv run ow-scrape build-dataset
uv run ow-rag index --mode hybrid && uv run ow-rag raft --n 15000
uv run ow-bench run <config...> && uv run ow-bench judge <config...> && uv run ow-bench report
```

Les entraînements se lancent sous WSL (`train/py.sh run <run>`, puis `train/export.sh <run>` pour le GGUF).
Les détails de chaque commande et les choix méthodologiques sont dans [`CLAUDE.md`](CLAUDE.md).

Matériel utilisé : RTX 5070 Ti 16 Go (génération, entraînement, banc) ; démo sur MacBook.
Le dossier `data/` (corpus, index, modèles) n'est pas versionné.

## Sources et licences

- [Overwatch Wiki (Fandom)](https://overwatch.fandom.com) — CC-BY-SA 3.0.
- [Liquipedia Overwatch](https://liquipedia.net/overwatch) — CC-BY-SA 3.0, attribution obligatoire
  (API : 1 requête / 2 s max, gzip, User-Agent avec contact).
- Notes de patch officielles © Blizzard Entertainment, utilisées à des fins de recherche.
- Modèles : Qwen3 (Apache 2.0) ; juge : Claude Sonnet. Développement assisté par Claude Code.
