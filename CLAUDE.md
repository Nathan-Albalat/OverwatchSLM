# OW-SLM — Small Language Model spécialisé Overwatch

Brain: Année INFO5/VTI

Projet d'UE (échéance : **début novembre 2026**). Objectif : montrer la pertinence d'un SLM dans certains
cas d'usage, en construisant un petit modèle spécialisé sur Overwatch (lore, gameplay, patchs, esport) et
en le comparant, sur un même jeu de questions, à des LLM locaux (7-14B) et à des modèles frontier.

## Matériel et environnement
- PC Windows 11 : RTX 5070 Ti **16 Go VRAM** (Blackwell, sm_120 → PyTorch avec **CUDA ≥ 12.8** obligatoire),
  Ryzen 7 9800X3D, 32 Go RAM, ~680 Go libres.
- Python 3.12 géré par **uv** (pas de Python système).
- **Smart App Control (Windows) est actif** et bloque les `.exe` du venv (`.venv/Scripts/python.exe`, `ow-*.exe`,
  `uv sync`/`uv run` : os error 4551). Lancer avec l'interpréteur de base uv + les paquets du venv :
  `PYTHONPATH=.venv/Lib/site-packages ~/.local/share/uv/python/cpython-3.12-windows-x86_64-none/python.exe -m <pkg>.cli ...`
  (dépendances : `uv add --no-sync X` puis `uv pip install X`). Les commandes `uv run ...` / `.venv/Scripts/python.exe`
  plus bas sont à lire avec cette substitution.
- **Traitements longs (génération)** : les lancer en processus indépendant (`Start-Process` PowerShell, sortie
  redirigée vers `data/qa/*.log`), jamais en tâche de fond Claude Code : celles-ci sont tuées quand la RAM libre
  tombe (le modèle Ollama occupe ~16 Go de RAM).
- Ollama local (`http://localhost:11434`), modèle de génération `qwen3.6:35b-a3b` (MoE, ~100 tok/s, `think:false`).
- Pas de WSL pour l'instant ; à installer pour le fine-tuning (Unsloth/bitsandbytes plus simples sous Linux).
- Le PC est mis en veille la nuit : **tout traitement long doit être reprenable** (append JSONL + skip des ids faits).

## Architecture du dépôt
```
scraper/            collecte + préparation du corpus (CLI `ow-scrape`)
  config.py         URLs, User-Agent, délais, chemins
  client.py         MediaWikiClient : session, rate limit, retries/backoff, maxlag, pagination `continue`
  fandom.py         Fandom : HTML rendu via action=parse (templates développés) ; `--refresh` / `--dry-run`
  liquipedia.py     Liquipedia : wikitext via prop=revisions par lots de 50 (jamais action=parse) ; idem refresh
  wikitext.py       wikitext -> texte (infobox en `Clé: valeur`, templates « nom » remplacés par leur 1er param.)
  clean.py          HTML/wikitext -> data/clean/*.jsonl (pages < 50 mots écartées)
  chunk.py          découpe par section -> data/chunks/chunks.jsonl (tag `sensitive`)
  stats.py          volumétrie -> data/stats.json
  common.py / cli.py   (common : listing, refresh = comparaison des revid + fusion atomique du brut)
gen/
  generate.py       génération Q/R via Ollama, reprenable (STOP / --until / --max-chunks / --sleep-after)
  templates.py      Q/R déterministes sans LLM (infobox héros/cartes/capacités Fandom ; joueurs/équipes/
                    tournois Liquipedia ; MVP/awards via AwardPrizePool du wikitext brut) -> data/qa/templates.jsonl
  build_dataset.py  filtrage + export (lecture seule de data/qa, relançable pendant une génération)
eval/
  test_set.jsonl|csv  jeu de test figé (227 questions) — NE JAMAIS l'utiliser pour l'entraînement
rag/                RAG + exemples RAFT (CLI `ow-rag`) ; index dans data/rag/ (ignore par git)
  common.py bm25.py embed.py   tokenisation, BM25 maison (numpy seul), embeddings Ollama /api/embed
  index.py retrieve.py         `index` ; retrieve(question, k, mode, exclude_ids) hybride RRF (repli bm25 sans embeddings)
  evaluate.py raft.py cli.py   hit@k sans LLM -> eval/report/retrieval.md ; exemples RAFT ; CLI
bench/              banc d'evaluation (CLI `ow-bench`) ; eval/ reste le dossier des donnees de test
  configs.toml      configurations (nom, backend ollama|openai|claude_cli|manual, modele, rag={k=5})
  prompts.py        SYSTEM_PROMPT (= gen.build_dataset) + format RAG (passages numerotes puis question), reutilise par RAFT
  backends.py       ollama (streaming, ttft, VRAM via /api/ps) | openai (llama.cpp/vLLM) | claude_cli (`claude -p`, abonnement) | manual
  run.py / judge.py / report.py / cli.py   run reprenable, LLM-juge par lots, tableaux
data/               (ignoré par git) raw/ clean/ chunks/ qa/ dataset/
```

### Commandes
```
uv run ow-scrape fandom|liquipedia [--limit N] [--first TITRE]   # collecte (reprenable)
uv run ow-scrape clean && uv run ow-scrape stats && uv run ow-scrape chunk
uv run ow-scrape generate [--only nonsensitive|sensitive|all] [--source ...] [--max-chunks N] [--until HH:MM] [--sleep-after]
uv run ow-scrape fandom|liquipedia --refresh --dry-run          # liste les pages dont le revid a changé (rien écrit)
uv run ow-scrape fandom|liquipedia --refresh                    # re-télécharge modifiées/nouvelles, fusionne le brut
uv run ow-scrape templates                                      # data/qa/templates.jsonl (~47k paires, < 2 s)
uv run ow-scrape build-dataset [--include-sensitive] [--test-threshold N] [--val-pct 5] [--seed 0]
```
Après un refresh : `clean` -> `chunk` -> `generate` (reprend seul : les chunks sont clés par `(id, revid)`) ->
`templates` -> `build-dataset`. `--out-dir` permet de tester un refresh dans un répertoire temporaire.
`uv run` resynchronise l'environnement : ne pas le lancer pendant une génération si `pyproject.toml` a changé
(le `.exe` du script est verrouillé) ; utiliser `.venv/Scripts/python.exe -m scraper.cli ...` ou `uv run --no-sync`.
### Banc d'évaluation (`ow-bench`, package `bench/`)
```
uv run ow-bench list
uv run ow-bench run <config...> [--limit N] [--ids G01,P03] [--category lore]   # eval/runs/<config>.jsonl, reprenable
uv run ow-bench judge <config...> [--judge claude_cli:sonnet | ollama:qwen3.6:35b-a3b]   # eval/judgments/
uv run ow-bench report [config...]       # eval/report/report.md + CSV
uv run ow-bench review-export [--per-config 15]   # eval/review/sample.csv (remplir human_verdict ; accord + kappa dans report)
uv run ow-bench export-questions <config> / import-answers <config> <csv>   # backend manual (frontier via interface web)
```
- Reprise par `(id, qhash)` (qhash = sha1 question+reponse) : apres mise a jour du test, seules les questions modifiees sont reposees.
  Arret : fichier `eval/runs/STOP` ou Ctrl+C. Ordre des questions melange (graine fixe).
- Frontier sans API payante : `claude -p` headless (cwd `data/bench_cwd/`, sans outils ni CLAUDE.md, prompt via stdin). Cout = equivalent API,
  tok/s et latence indicatifs. Limite d'abonnement detectee -> arret propre, relancer plus tard.
- RAG : une config avec `rag` appelle `rag.retrieve.retrieve(question, k) -> [{'id','text'}]` (package `rag/`, voir section RAG/RAFT).
- Juge : verdicts correct/partial/incorrect/abstained (unanswerable : correct/hallucinated), la reference fait foi. Score : correct=1, partial=0.5.
- Si `uv sync` echoue (build bloque par une strategie de controle d'application Windows), lancer `.venv/Scripts/python.exe -m bench.cli ...`.

### RAG et exemples RAFT (`ow-rag`, package `rag/`)
```
.venv/Scripts/python.exe -m rag.cli index --mode bm25|hybrid [--embed-model qwen3-embedding:0.6b]  # data/rag/ ; hybrid = GPU (Ollama), reprenable (data/rag/STOP)
.venv/Scripts/python.exe -m rag.cli query "question" [--mode bm25|dense|hybrid] [--k 5]        # inspection manuelle
.venv/Scripts/python.exe -m rag.cli eval [--mode ...] [--k 1,3,5,10]       # hit@k test + 1000 paires val -> eval/report/retrieval.md
.venv/Scripts/python.exe -m rag.cli raft [--n 15000] [--k 4] [--p-oracle 0.8] [--mode ...] [--out-dir D]   # data/dataset/raft_{train,val}.jsonl + raft_stats.json
```
- Index = tous les chunks courants (sensibles et faible valeur inclus) + **fiches de faits** (`facts:<source>:<pageid>:<n>`) issues des templates
  sans `chunk_id` OU de categorie `award` (MVP/prize pools : absents du texte du chunk) -> trouvent E41-E43.
- Recherche : BM25 + dense (qwen3-embedding:0.6b via Ollama, requetes prefixees `Instruct: ...
Query: `), fusion RRF (k=60), max 2 passages/page.
  Sans `data/rag/emb.npy`, tout mode retombe sur bm25 (message explicite).
- Mise a jour : cache d'embeddings par sha1(texte) (`data/rag/emb_cache*`) : apres le refresh, `index` n'encode que les textes nouveaux/modifies et
  affiche « N encodes, M repris du cache, duree » = cout de mise a jour du RAG pour le rapport.
- RAFT : source `data/dataset/pairs.jsonl` (paires finales, exportees par `build-dataset`), ~10 % de templates ; avec p=0.8 oracle + k-1 distracteurs du vrai
  retriever, sinon k distracteurs et refus fixe : tout distracteur qui pourrait contenir la reponse (elements cles de la reponse absents de la question, mots entiers,
  passage citant >= 50 % des entites de la question) est ecarte et remplace par le suivant (pool k+16) ; si la reponse est dans presque tous les
  candidats, exemple `answer_in_distractor` (reponse gardee). Test 600 ex. : 447 oracle / 117 refus / 6 answer_in_distractor (ancien critere : 55 % de « refus annules »).
  Format de prompt = `bench.prompts.build_messages` (identique a l'eval). Tirage deterministe par (graine, id) : reprise sans doublon.

### Jeu de données (`build-dataset` -> `data/dataset/`)
`train.jsonl` / `val.jsonl` (format chat `messages`, split 95/5 **par page**), `cpt.jsonl` (`{"text"}` par chunk, hors
faible valeur), `sample_review.csv` (100 paires, `;`, UTF-8 BOM, colonne `verdict` à remplir), `stats.json` (comptes à
chaque étape), `test_coverage.jsonl` (fait du test couvert ou non, indicatif).
Étapes : revid courant -> sensibles écartés (défaut, `--include-sensitive` pour les garder) -> format -> phrases « meta »
-> faible valeur (`LOW_VALUE_RULES` dans `build_dataset.py` : listes de cosmétiques, paliers de Battle Pass, transcripts,
citations vocales, défis d'événements, succès ; `keep` = fraction conservée) -> ancrage des nombres (paires LLM) ->
doublons (exact puis `rapidfuzz` par page) -> **proximité avec le test** (token_set_ratio ≥ 80 ET ratio ≥ 70 ET mêmes
nombres ET ≥ 60 % des entités/mots de contenu : le token_set_ratio seul confond « ultime de Genji » et « ultime de
Freja »). Les templates (tournois ~33k) dominent en volume : à sous-échantillonner au besoin pour l'entraînement.
Couverture du test : heuristique documentée en tête de `build_dataset.py` (question proche OU entités/nombres de la
réponse attendue retrouvés dans une paire) ; sert à découper les résultats couverts / non couverts.

Arrêt propre de la génération : créer `data/qa/STOP` (le supprimer avant de reprendre), ou Ctrl+C
(1er = finit le chunk en cours). Reprise : relancer la même commande.

## Données
| Source | Licence | Pages gardées | Volume |
|---|---|---|---|
| Overwatch Fandom wiki | CC-BY-SA | 2 237 | ~2,7 M mots (~3,6 M tokens) |
| Liquipedia Overwatch | CC-BY-SA 3.0 (attribution obligatoire) | ~5 577 | ~1,1 M mots (~1,5 M tokens) |

- Chunks : **14 161** (9 888 non sensibles / 4 273 sensibles = pages héros et notes de patch).
- Règles Liquipedia : ≤ 1 req / 2 s, `action=parse` ≤ 1 / 30 s (donc interdit à grande échelle), UA avec contact, gzip.
- Limites connues :
  - **Vainqueurs de tournois absents du texte** (calculés depuis les brackets/LPDB) ; une extraction naïve des
    `TeamCard placement=1` donne des résultats **faux** (ex. OWL 2018). Pas de question « qui a gagné X » tant
    que les brackets ne sont pas parsés proprement.
  - MVP et prize pools détaillés ne sont que dans les templates du wikitext brut (`AwardPrizePool`).
  - 12 300 pages Liquipedia écartées du texte (résultats/brackets en templates) mais conservées en brut.
  - Le jour du scraping fixe la « date de connaissance » du modèle : les stats de héros changent à chaque patch.

## Jeu de test (`eval/test_set.jsonl`)
227 questions en **anglais** (comme le corpus), validées par l'utilisateur, champs
`id, category, temporal, question, answer, source, note`.
- Catégories : lore 51, gameplay 50, esport 43, patch 42, maps_modes 25, **unanswerable 16**.
- `temporal=true` (66) : faits postérieurs à ~avril 2025 → pièges pour les modèles frontier (date de coupure).
- `unanswerable` (U01-U16) : événements futurs, entités inventées, prémisses fausses → mesure l'hallucination
  (comportement attendu : « je ne sais pas » ou correction de la prémisse).
- E41-E43 : réponse uniquement dans les templates bruts (mesure l'apport de l'extraction des templates).
- Règle : toute paire d'entraînement trop proche d'une question du test est supprimée (`build-dataset`, voir stats.json).
- À mettre à jour après le refresh Saison 5 : T04, T42, U08 et les questions de valeurs « actuelles »
  (T14, T18, T21, T22, T27, T39, G06, G10, G18, G23, G30, G35).

## Choix méthodologiques

### Pourquoi fine-tuner un modèle existant plutôt qu'entraîner de zéro
~5 M tokens, c'est trop peu pour pré-entraîner un modèle utile (il produirait du texte plausible sans savoir
répondre). On part d'un petit modèle de base (Qwen3 1.7B/4B, Gemma 3, Llama 3.2…) adapté par LoRA/QLoRA.
Un mini-modèle « from scratch » (nanoGPT) reste une annexe pédagogique facultative.

### Génération des données d'entraînement
- **Qwen local** (gratuit, licence Apache 2.0 → pas de restriction sur l'usage des sorties pour entraîner).
  Écartés : API Claude (coût + conditions d'usage des sorties à vérifier) ; abonnement Claude Code (chaque
  appel recharge un gros contexte → limites atteintes en quelques heures, inadapté à ~10k appels).
- 5-8 paires par chunk, ancrées dans le passage, questions autonomes (le sujet est nommé), faits d'équilibrage
  datés. ~7,5 paires/chunk, ~6 s/chunk → ~74k paires brutes pour les chunks non sensibles (à filtrer vers 20-40k).
- Les chunks **sensibles** (héros, patchs) sont générés **après** la Saison 5 (sortie 6 oct. 2026) et le
  refresh des wikis (~8-9 oct.), pour figer une base à jour.

### Comment le modèle peut répondre sur un fait du wiki (trois cas)
| Cas | Exemple | Comportement attendu |
|---|---|---|
| A. Fait couvert par une Q/R, question reformulée | « Genji's ultimate? » vu, « Quel est l'ultime de Genji ? » posé | Bon (généralisation de la formulation) |
| B. Fait dans le wiki, aucune Q/R ne le couvre | Détail d'une page non repris en Q/R | Peu fiable en fine-tuning seul |
| C. Fait absent du corpus | Saison 6, entités inventées | Hallucination probable si rien n'est prévu |

Méthodes et limites :
| Méthode | Principe | Limites |
|---|---|---|
| **Fine-tuning Q/R (SFT)** | Le modèle apprend les faits sous forme Q/R | Retient mal ce qui n'est pas en Q/R (cas B) ; « reversal curse » (A→B appris ≠ B→A) ; capacité de mémorisation limitée d'un petit modèle ; oubli partiel des connaissances générales ; réentraînement à chaque mise à jour ; hallucine avec aplomb (cas C) |
| **Génération exhaustive par fait** (option) | Qwen liste tous les faits atomiques d'un chunk, puis 2-3 Q/R par fait, dans les deux sens | ×2-3 de temps de génération ; ne règle ni la mise à jour ni l'hallucination |
| **Pré-entraînement continu (CPT)** sur le texte brut (+ paraphrases) avant le SFT | Le modèle « lit » tout le wiki | Gain modeste : un fait vu une fois sous une forme est difficile à restituer ; coût ~1 h ; risque d'oubli |
| **RAG** | On récupère 3-5 chunks pertinents (embeddings locaux) et on les donne avec la question | Dépend de la qualité de la recherche (si le bon passage n'est pas retrouvé, échec) ; contexte plus long → latence ; un petit modèle non entraîné lit mal les passages bruités |
| **RAFT** (choix principal) | Fine-tuning au format RAG : question + passages (dont distracteurs, et parfois sans la réponse → cible « je ne sais pas ») → réponse | Toujours dépendant du retriever ; données d'entraînement un peu plus complexes à construire ; plus lent à l'inférence que le SFT seul |

**Décision** : configuration principale **SLM + RAG + RAFT** (couvre les cas A, B et C, mise à jour par
simple réindexation, moins d'hallucination). La génération Q/R actuelle sert aux deux (SFT et exemples RAFT).
La génération exhaustive par fait est une option si du temps de calcul se libère.

### Configurations à comparer
1. SLM de base (sans adaptation) — 2. SLM + SFT — 3. SLM + CPT + SFT (expérimental) — 4. SLM + RAG —
5. **SLM + RAFT (+ RAG)** — 6. LLM locaux 7-14B avec et sans RAG — 7. un ou deux modèles frontier.
Analyse découpée en faits **couverts / non couverts** par les données d'entraînement (calculé
automatiquement après construction du dataset), plus les questions temporelles et sans réponse.
Mesures : exactitude (LLM-juge + vérification manuelle d'un échantillon), taux d'hallucination sur
`unanswerable`, latence, tokens/s, VRAM, coût par requête, coût de mise à jour (pages re-scrapées, minutes de
génération et d'entraînement après la Saison 5).

## Feuille de route
- [x] Scraping Fandom + Liquipedia, nettoyage, stats
- [x] Jeu de test figé (227 questions)
- [x] Lot 1 : correction des patchs Liquipedia, chunking, générateur reprenable
- [ ] Génération Qwen des chunks non sensibles (en cours, reprenable)
- [x] Lot 2 : Q/R par templates (infobox, MVP), mode `--refresh` (revid), filtrage (doublons, ancrage,
      proximité avec le test, catégories à faible valeur comme les paliers de Battle Pass), export
      `data/dataset/{train,val}.jsonl` + `cpt.jsonl` + couverture du test (code prêt ; refresh réel à lancer
      après la sortie de la Saison 5, `build-dataset` à relancer en fin de génération)
- [ ] Après Saison 5 (6 oct.) : refresh, chunks sensibles, mise à jour des réponses du test
- [ ] Index RAG (embeddings locaux) + construction des exemples RAFT (code prêt et testé en bm25 ; reste : embeddings Ollama quand le GPU est libre, `eval` dense/hybrid, `raft --n 15000`)
- [ ] Installation WSL2 + PyTorch CUDA 12.8 + Unsloth, fine-tunings (SFT, CPT+SFT, RAFT)
- [x] Banc d'évaluation (`bench/`, code prêt ; vérifié sur Claude Sonnet, backend Ollama non testé)
- [ ] Lancer le banc sur toutes les configurations (SLM fine-tunés, LLM locaux, frontier), vérification manuelle, rédaction

## Conventions
- Code et commentaires en français, sans accents dans les messages console (encodage Windows).
- Toute étape longue écrit en append JSONL avec flush par élément et sait reprendre.
- `data/` n'est jamais commité ; `eval/` et le code le sont. Citer Fandom et Liquipedia (CC-BY-SA) dans tout livrable.
