# OW-SLM — Dossier de rendu (résultats, coûts, complexité, historique)

Document de travail pour le rendu final de l'UE (échéance début novembre 2026). Il rassemble les chiffres mesurés,
les comparaisons entre approches, les coûts et la complexité de mise en œuvre, et l'historique du projet.
**Mis à jour au fil des entraînements** : les sections marquées *(à compléter)* attendent des runs à venir.

Sources des chiffres : `eval/report/report.md` (banc), `eval/report/retrieval_hybrid.md` (recherche),
`eval/report/training.md` (entraînements), `data/stats.json`, `data/dataset/stats.json`,
`data/dataset/raft_stats.json`, journaux `data/qa/*.log`, historique git.

---

## 1. Objectif et question posée

Montrer dans quels cas un **petit modèle de langage (SLM, 1,7-4 B paramètres)** est pertinent face aux LLM locaux
plus gros (14 B) et aux modèles frontier (Claude Sonnet / Opus), sur un domaine de niche qui évolue vite :
**Overwatch** (lore, gameplay, patchs, esport). Les critères comparés sont l'exactitude, l'hallucination,
la latence, la mémoire, le coût par requête, le coût de construction et le coût de mise à jour.

Configuration principale visée : **SLM + RAG + RAFT** (fine-tuning au format RAG).

---

## 2. Données

### 2.1 Corpus

| Source | Licence | Pages brutes | Pages gardées | Volume |
|---|---|---|---|---|
| Overwatch Fandom wiki | CC-BY-SA | 2 716 | 2 237 | 2,75 M mots (~3,6 M tokens) |
| Liquipedia Overwatch | CC-BY-SA 3.0 | 17 900 | 5 578 | 1,14 M mots (~1,5 M tokens) |
| Notes de patch officielles Blizzard (6 oct. 2026) | © Blizzard, citer la source | 1 | 1 | ~4 800 mots |

- Pages écartées : moins de 50 mots. 12 322 pages Liquipedia ne contiennent que des templates (résultats, brackets) : elles sont conservées en brut, sans texte exploitable.
- **14 208 chunks**, découpés par section : 9 891 non sensibles et 4 317 sensibles (pages héros et notes de patch, générées après la Saison 5).
- Les notes Blizzard sont découpées finement, un chunk par héros, soit 42 chunks (voir §7, problème n°6).

### 2.2 Jeu de test (figé, jamais utilisé pour l'entraînement)

**235 questions en anglais**, validées à la main :

| Catégorie | n | Remarque |
|---|---|---|
| lore | 51 | |
| gameplay | 50 | |
| esport | 43 | |
| patch | 50 | dont S01-S08, patch Saison 5 du 6 oct. 2026 |
| maps_modes | 25 | |
| unanswerable | 16 | événements futurs, entités inventées, prémisses fausses → mesure l'hallucination |

- 74 questions **temporelles** portent sur des faits postérieurs à ~avril 2025, au-delà de la date de coupure des modèles frontier.
- E41-E43 ont leur réponse uniquement dans les templates bruts.
- Toute paire d'entraînement trop proche d'une question du test est supprimée : 224 paires retirées.

### 2.3 Données d'entraînement générées

- **Q/R LLM** : `qwen3.6:35b-a3b` en local (Ollama, licence Apache 2.0), 5 à 8 paires par chunk, ancrées dans le passage. Au total, 13 767 chunks générés, soit 100 482 paires brutes et 6,0 M tokens de sortie.
- **Q/R par templates**, sans LLM (infobox, joueurs, équipes, tournois, MVP) : 47 314 paires en moins de 2 s.
- **Filtrage** : 147 796 paires brutes donnent **107 271 paires finales** (102 160 en train, 5 111 en val, split par page).

| Étape | Paires retirées |
|---|---|
| Périmées (revid) | 6 181 |
| Plafond tournois mineurs | 27 000 |
| Faible valeur (citations vocales, cosmétiques…) | 3 331 |
| Méta | 1 333 |
| Ancrage des nombres | 741 |
| Doublons exacts et flous | ~1 700 |
| Proximité avec le test | 224 |

- **CPT** : 12 360 chunks de texte brut, hors faible valeur.
- **Couverture du test** : 165 faits sur 219 (heuristique) sont présents dans les données d'entraînement. Les résultats sont découpés en « couvert » / « non couvert ».

### 2.4 Exemples RAFT

- 15 000 exemples (train 14 250 / val 748), k = 4 passages, p_oracle = 0,8, retriever hybride.
- **Train v1**, utilisé pour RAFT 4B : 11 446 avec le passage de réponse (oracle), 2 691 refus et 113 `answer_in_distractor`. 6 624 distracteurs qui contenaient la réponse ont été remplacés. Les exemples font en moyenne ~1 560 tokens (max 2 746) ; la loss ne porte que sur la réponse, soit 1,2 % des tokens.
- **Train v2** (13 oct., après correction du problème n°7, pour les runs suivants) : 11 434 oracle / 2 700 refus / 116 `answer_in_distractor`, 6 591 distracteurs remplacés.
- Sans oracle, la cible est toujours un refus. Les distracteurs susceptibles de contenir la réponse sont écartés, pour que ce refus soit justifié.

---

## 3. Configurations comparées

| # | Configuration | Modèle | Contexte |
|---|---|---|---|
| 1 | SLM de base | Qwen3-1.7B / Qwen3-4B (GGUF Q4_K_M Unsloth) | question seule |
| 2 | SLM + SFT | Qwen3-4B + LoRA (Q/R) | *(à venir)* |
| 3 | SLM + CPT + SFT | Qwen3-4B + LoRA (texte brut puis Q/R) | *(à venir)* |
| 4 | SLM + RAG | Qwen3-1.7B / 4B de base | 4 passages |
| 5 | **SLM + RAFT + RAG** | Qwen3-4B (fait), 1.7B *(à venir)* | 4 passages |
| 6 | LLM local | Qwen3-14B (Ollama) | ± 5 passages |
| 7 | Frontier | Claude Sonnet, Claude Opus (`claude -p`) | Sonnet ± 5 passages |

- **Évaluation** : un juge LLM (Claude Sonnet) note chaque réponse correct, partial, incorrect ou abstained ; pour les questions sans réponse, correct ou hallucinated. La référence fait foi. Score = correct + 0,5 × partial.
- La température vaut 0 et le mode thinking est désactivé pour les modèles Qwen.
- **Biais à signaler** :
  - les SLM + RAG utilisent k = 4, comme les exemples RAFT, alors que le 14B et Sonnet + RAG utilisent k = 5 ;
  - le test a été écrit à partir du même corpus que l'index RAG, ce qui favorise les bras RAG ;
  - la vérification manuelle du juge reste à faire (§8).

---

## 4. Résultats (banc du 13 oct. 2026, 235 questions)

### 4.1 Exactitude globale

| Configuration | Score % | Correct | Partiel | Incorrect | Abstention | Halluc. (/16) |
|---|---|---|---|---|---|---|
| Claude Opus | 56,0 | 120 | 23 | 21 | 71 | 0 |
| Claude Sonnet | 43,2 | 91 | 21 | 27 | 96 | 0 |
| **Claude Sonnet + RAG** (k=5) | **93,8** | 217 | 7 | 0 | 11 | 0 |
| Qwen3-14B | 12,6 | 21 | 17 | 170 | 17 | 10 |
| Qwen3-14B + RAG (k=5) | 90,6 | 207 | 12 | 7 | 9 | 0 |
| Qwen3-4B | 4,7 | 5 | 12 | 195 | 11 | 12 |
| **Qwen3-4B + RAG** (k=4) | **86,6** | 194 | 19 | 14 | 8 | 0 |
| **Qwen3-4B RAFT + RAG** (k=4) | 83,6 | 187 | 19 | 9 | 20 | 0 |
| Qwen3-1.7B | 2,3 | 3 | 5 | 203 | 10 | 14 |
| Qwen3-1.7B + RAG (k=4) | 80,9 | 183 | 14 | 31 | 4 | 3 |
| Qwen3-4B + SFT | *(à venir)* | | | | | |
| Qwen3-4B + CPT + SFT | *(à venir)* | | | | | |
| Qwen3-1.7B RAFT + RAG | *(à venir)* | | | | | |

### 4.2 Par catégorie (score %)

| Configuration | lore | gameplay | esport | patch | maps | unanswerable |
|---|---|---|---|---|---|---|
| Claude Opus | 72,5 | 85,0 | 26,7 | 13,0 | 72,0 | 100 |
| Claude Sonnet | 57,8 | 69,0 | 12,8 | 4,0 | 56,0 | 100 |
| Claude Sonnet + RAG | 95,1 | 100 | 81,4 | 92,0 | 100 | 100 |
| Qwen3-14B | 18,6 | 9,0 | 2,3 | 8,0 | 18,0 | 37,5 |
| Qwen3-14B + RAG | 95,1 | 94,0 | 79,1 | 85,0 | 100 | 100 |
| Qwen3-4B + RAG | 92,2 | 89,0 | 72,1 | 81,0 | 98,0 | 100 |
| Qwen3-4B RAFT + RAG | 84,3 | 87,0 | 68,6 | 81,0 | 96,0 | 100 |
| Qwen3-1.7B + RAG | 83,3 | 86,0 | 67,4 | 75,0 | 100 | 81,2 |

### 4.3 Questions temporelles et faits couverts (questions répondables, score %)

| Configuration | temporel (74) | non temporel (145) | couvert (165) | non couvert (54) |
|---|---|---|---|---|
| Claude Opus | 15,5 | 71,7 | 58,5 | 35,2 |
| Claude Sonnet | 5,4 | 56,2 | 46,4 | 16,7 |
| Claude Sonnet + RAG | 92,6 | 93,8 | 95,2 | 88,0 |
| Qwen3-14B + RAG | 87,2 | 91,4 | 91,8 | 84,3 |
| Qwen3-4B + RAG | 79,7 | 88,6 | 87,3 | 80,6 |
| Qwen3-4B RAFT + RAG | 79,7 | 83,8 | 85,2 | 74,1 |
| Qwen3-1.7B + RAG | 75,0 | 83,8 | 82,1 | 76,9 |

### 4.4 Saison 5 (S01-S08, patch du 6 oct. 2026, absent de tout modèle pré-entraîné)

| Configuration | Correctes | Détail |
|---|---|---|
| Opus / Sonnet sans RAG | 0/8 | abstention (Opus : 1 erreur sur S02) |
| Sonnet + RAG, 14B + RAG | 7/8 | S08 en abstention |
| 4B + RAG | 5/8 + 1 partielle | S03 partielle, S04 incorrecte, S08 abstention |
| 4B RAFT + RAG | 5/8 + 1 partielle | S03 partielle, S02 et S08 abstentions (S04 corrigée par rapport au 4B de base) |
| 1.7B + RAG | 6/8 | S06 et S08 incorrectes |

S08 (mode Halloween) est raté partout à cause du retriever : le mot « Halloween » n'apparaît qu'une fois dans un passage de 457 mots, et les pages Fandom génériques passent devant. Nous l'avons laissé tel quel et le citons comme limite ; la question n'a pas été réécrite pour s'adapter au retriever.

### 4.5 Performance d'inférence (RTX 5070 Ti, Ollama, Q4_K_M)

| Configuration | Latence p50 (s) | p95 (s) | TTFT p50 (s) | tok/s | VRAM (Go) | Coût / requête |
|---|---|---|---|---|---|---|
| Claude Opus | 5,78 | 11,65 | 2,62 | ~200* | — | 0,0148 $ (équiv. API) |
| Claude Sonnet | 5,62 | 11,52 | 3,25 | ~390* | — | 0,0084 $ |
| Claude Sonnet + RAG | 3,14 | 5,11 | 1,69 | ~264* | — | 0,0203 $ |
| Qwen3-14B + RAG | 1,24 | 1,89 | 0,87 | 75 | 10,5 | 0 (local) |
| Qwen3-4B + RAG | 0,46 | 0,78 | 0,29 | 193 | 3,9 | 0 |
| Qwen3-4B RAFT + RAG | 0,38 | 0,50 | 0,27 | 204 | 3,9 | 0 |
| Qwen3-1.7B + RAG | 0,24 | 0,39 | 0,16 | 362 | 2,2 | 0 |

\* Pour `claude -p`, les débits et latences sont indicatifs : ils incluent le réseau et les tokens de réflexion. Le prompt RAG fait ~2 100 tokens pour les Qwen (k=4) et ~4 800 pour Sonnet (k=5). Les réponses des modèles RAFT sont plus courtes (21 tokens médians contre 29 pour le 4B de base + RAG).

### 4.6 Ce que montrent les résultats à ce stade

1. **Le RAG fait l'essentiel du gain**, quelle que soit la taille :
   - le 4B passe de 4,7 % à 86,6 % ;
   - le 1.7B passe de 2,3 % à 80,9 % ;
   - le 14B passe de 12,6 % à 90,6 %.
   Sans RAG, tous les modèles locaux hallucinent massivement : 62 à 88 % sur les questions sans réponse.
2. **Un SLM de 4B avec RAG se place à 7 points de Sonnet + RAG et à 4 points du 14B + RAG**, pour un coût marginal nul. Il est ~7 fois plus rapide que Sonnet + RAG et ~2,7 fois plus rapide que le 14B, avec 2,7 fois moins de VRAM. Il tient sur un portable (démo Mac).
3. **Les frontier sans RAG ne connaissent pas l'actualité du domaine.** Ils obtiennent 5 à 16 % sur les questions temporelles et 0/8 sur la Saison 5. En revanche, ils s'abstiennent au lieu d'halluciner (0 % d'hallucination, 32 à 44 % d'abstention).
4. **Le RAFT 4B ne bat pas le 4B de base + RAG en score (83,6 % contre 86,6 %), mais il change de comportement** :
   - moins d'erreurs (9 contre 14), plus d'abstentions (20 contre 8) ;
   - sur les 14 erreurs du 4B + RAG, 6 deviennent des abstentions ;
   - en contrepartie, il s'abstient sur 6 questions que le modèle de base réussissait (G41, G43, T14, G24, S02, E08) ;
   - sur la Saison 5, il fait jeu égal avec le modèle de base (5 correctes + 1 partielle) : il corrige S04 mais s'abstient sur S02 ;
   - ses réponses sont plus courtes et sa latence p95 plus basse.
   Hypothèses à tester : la part de refus (19 %) est peut-être trop élevée, et le modèle refuse peut-être quand la réponse n'apparaît dans le passage que sous une forme indirecte. Pistes : p_oracle à 0,9, ou plus d'exemples `answer_in_distractor`.
5. **Le 1.7B + RAG est le seul bras RAG qui hallucine** (3 sur 16) : un très petit modèle lit moins bien des passages bruités. C'est précisément le cas visé par RAFT 1.7B *(à venir)*.

---

## 5. Coûts

### 5.1 Coût de construction (une fois)

| Poste | Mesure | Ressource |
|---|---|---|
| Collecte Fandom + Liquipedia | durée non mesurée, limitée par les règles de politesse (Fandom ~1 req/s ; Liquipedia ≤ 1 req / 2 s par lots de 50 pages, pas de `action=parse`) | réseau |
| Nettoyage, découpe, statistiques | moins d'une minute chacun | CPU |
| Génération Q/R (13 767 chunks) | **25,7 h GPU cumulées**, 6,0 M tokens de sortie, ~80-105 tok/s, ~6-8 s/chunk | GPU 16 Go, ~16 Go RAM |
| Q/R par templates | moins de 2 s | CPU |
| Construction du dataset | ~1-2 min | CPU |
| Index RAG complet (embeddings `qwen3-embedding:0.6b`) | 343 s pour 14 718 textes | GPU |
| Exemples RAFT (15 000, hybride) | ~7 min (~36 ex/s) | GPU (embeddings des requêtes) |
| **Entraînement RAFT Qwen3-4B** (QLoRA r=32, 1 epoch) | **3 h 22**, 0,85 s/ex, 2 322 tok/s, pic VRAM 13,9 Go | GPU (WSL2) |
| Export GGUF Q4_K_M (4B) | 7 min (2,5 Go) | GPU / CPU |
| Entraînement RAFT 1.7B / SFT 4B / CPT / CPT+SFT | *(à venir ; estimations : ~1 h 30 / ~1 h 40 par epoch / ~1 h / ~3 h 20)* | |
| Banc local (235 q.) | 1 à 5 min par configuration | GPU |
| Banc frontier (235 q.) | ~24 min par config sans RAG, ~14 min avec RAG | abonnement |
| Jugement (235 q.) | ~1,5 min par config (lots de 15, ~5 s/lot) | abonnement |

**Coût équivalent API** des runs frontier (abonnement Claude Code, pas une dépense réelle) :

| Config | Total (236 requêtes) | Par requête |
|---|---|---|
| Opus | 3,49 $ | 0,0148 $ |
| Sonnet | 1,99 $ | 0,0084 $ |
| Sonnet + RAG | 4,79 $ | 0,0203 $ |

Le coût des jugements n'est pas enregistré dans les fichiers.

### 5.2 Coût d'usage (par requête)

- **SLM local** :
  - coût marginal nul (électricité exceptée, *à mesurer : `nvidia-smi --query-gpu=power.draw`*) ;
  - 0,4 s par réponse avec RAG ;
  - 2,2 à 3,9 Go de VRAM, possible sur un portable.
- **Frontier** : 0,008 à 0,02 $ par requête en équivalent API, 3 à 6 s de latence, dépendance au réseau et au fournisseur. Ordre de grandeur pour 10 000 requêtes par jour avec Sonnet + RAG : ~200 $ par jour.

### 5.3 Coût de mise à jour (Saison 5, sortie le 6 oct. 2026)

| Étape | Mesure |
|---|---|
| Détection des pages modifiées (comparaison des revid) | Fandom : 52 modifiées + 1 nouvelle ; Liquipedia : 167 modifiées + 9 nouvelles |
| Délai des wikis | Fandom partiel au bout de 5 jours (Ana, Shion, Eichenwalde non mis à jour) ; Liquipedia crée ses pages de patch par lots, avec **2 à 4 semaines de retard** → ajout des notes officielles Blizzard (scraper dédié, une page HTML par mois, exécution en quelques secondes) |
| Régénération Q/R | 839 chunks en 1 h 32 (6 544 paires), puis 42 chunks Blizzard en ~5 min (249 paires) |
| **Mise à jour de l'index RAG** | **~6 s** (107 textes encodés, le reste repris du cache sha1), puis 3 s après la redécoupe Blizzard |
| Réentraînement | RAFT 4B : 3 h 22 ; SFT : *(à mesurer)* |

**Lecture.** Pour un bras RAG, la mise à jour coûte quelques secondes de réindexation, et le modèle répond aussitôt sur la Saison 5 (6 à 7 questions sur 8). Un bras SFT, lui, exige de régénérer les Q/R puis de réentraîner, soit plusieurs heures de GPU à chaque patch. Un frontier attend la prochaine version du modèle.

---

## 6. Complexité de mise en œuvre

### 6.1 Par approche

| Approche | Composants nécessaires | Effort de développement | Calcul initial | Mise à jour | Risque principal |
|---|---|---|---|---|---|
| SLM de base | Ollama | nul | nul | impossible | hallucination massive (75-88 %) |
| SLM + RAG | corpus, découpe, index BM25 + embeddings, retriever | moyen (`rag/`, 786 lignes) | ~6 min d'embeddings | secondes | dépend du retriever (S08) |
| SLM + SFT | corpus, génération Q/R, filtrage, QLoRA | élevé (`gen/` 1 169 lignes + `train/` 375) | ~26 h de génération + entraînement | heures (génération + entraînement) | oubli, faits non couverts, hallucination assurée |
| SLM + CPT + SFT | idem + passe de texte brut | élevé | + ~1 h | heures | gain modeste attendu |
| **SLM + RAFT + RAG** | tout ce qui précède + construction des exemples RAFT | le plus élevé | génération + 7 min + 3 h 22 | secondes (index), réentraînement optionnel | sur-abstention observée |
| LLM local 14B + RAG | RAG + GPU 12 Go ou plus | moyen | idem RAG | secondes | latence ×2,7, VRAM ×2,7 |
| Frontier (+ RAG) | abonnement / API (+ RAG) | faible | nul | dépend du fournisseur | coût récurrent, données envoyées à un tiers, connaissances datées sans RAG |

### 6.2 Taille du code (Python)

| Package | Rôle | Fichiers | Lignes |
|---|---|---|---|
| `scraper/` | collecte, nettoyage, découpe, refresh, Blizzard | 12 | 1 021 |
| `gen/` | génération Q/R, templates, dataset | 4 | 1 169 |
| `rag/` | BM25, embeddings, retriever hybride, RAFT | 9 | 786 |
| `bench/` | banc, backends, juge, rapport | 8 | 888 |
| `train/` | QLoRA SFT/CPT/RAFT, export GGUF | 6 | 375 |
| **Total** | | 39 | **~4 240** |

### 6.3 Contraintes d'environnement rencontrées

- **Smart App Control** (Windows) bloque les `.exe` des venv, `uv run` et `uv sync`. Contournement : interpréteur de base uv avec `PYTHONPATH` vers les paquets du venv.
- **Fine-tuning sous WSL2** (Ubuntu 24.04) : Unsloth et bitsandbytes s'utilisent mal sous Windows, et le GPU Blackwell exige CUDA ≥ 12.8.
- **Mémoire** : le modèle de génération occupe ~16 Go de RAM, et les tâches de fond longues sont tuées si la RAM manque. Tous les traitements longs sont donc lancés en processus indépendants et sont **reprenables** (append JSONL, fichiers STOP, `--resume`).
- **VRAM de 16 Go partagée** entre Ollama (génération, embeddings, banc) et l'entraînement : il faut décharger les modèles avant chaque entraînement (pic SFT 4B avec packing : 14,3 Go).

---

## 7. Historique du projet

| Date | Étape | Commit(s) |
|---|---|---|
| avant le 8 oct. | Choix du sujet, collecte Fandom + Liquipedia, nettoyage, découpe ; écriture du jeu de test (227 q.) ; décision méthodologique (fine-tuning d'un modèle existant, RAG + RAFT) | — |
| 8 oct. | Premiers commits : corpus, jeu de test figé, génération Q/R + templates + dataset, banc `ow-bench`, RAG hybride + RAFT | `3e38c62` → `9e083d4` |
| 9 oct. | Indexation des embeddings (343 s) ; comparaison BM25 / dense / hybride → hybride retenu | `6ce3029` |
| 10 oct. | Diagnostic Smart App Control, lancement des traitements longs ; génération des chunks sensibles | `09011ab` |
| 11 oct. | Correction du critère RAFT (55 % de « refus annulés » à tort) ; banc frontier (Sonnet, Sonnet + RAG, Opus) | `70f3980`, `3c74eeb` |
| 12 oct. | WSL2 + Unsloth ; package `train/` ; banc local (1.7B, 4B, 14B ± RAG) ; refresh Saison 5 + notes Blizzard + S01-S08 ; correction de la découpe Blizzard ; dataset final ; exemples RAFT | `1991b13` → `1790a9a` |
| 12-13 oct. | **Premier entraînement complet : RAFT Qwen3-4B** (3 h 22), export, banc | `aa00b41` |
| *(à venir)* | RAFT 1.7B, SFT 4B, CPT + SFT, vérification manuelle du juge, rédaction | |

### 7.1 Décisions méthodologiques (et pourquoi)

| Décision | Raison |
|---|---|
| Fine-tuning QLoRA d'un modèle existant, pas d'entraînement from scratch | ~5 M tokens de corpus, beaucoup trop peu pour pré-entraîner un modèle utile |
| Qwen3-4B pour tous les bras, 1.7B en comparaison RAFT | compromis qualité / démo sur Mac (GGUF 1,1 à 2,5 Go) / temps d'entraînement |
| Données générées par un Qwen local, pas par l'API Claude | coût (~10 000 appels), conditions d'usage des sorties ; Apache 2.0 |
| Frontier via `claude -p` (abonnement) | pas d'API payante ; latence et tokens servent d'indicateurs de vitesse |
| RAG hybride BM25 + dense (RRF) | BM25 rate les reformulations, le dense rate les correspondances exactes |
| RAFT : refus garanti sans oracle | sans filtrage, un « refus » pouvait être faux (la réponse était dans un distracteur) |
| Chunks sensibles générés **après** la Saison 5 | figer une base à jour et mesurer un vrai coût de mise à jour |
| Notes officielles Blizzard en plus des wikis | les wikis ont 2 à 4 semaines de retard sur les patchs |
| Garder S08 malgré l'échec du retriever | ne pas ajuster le test au système évalué |

### 7.2 Problèmes rencontrés et corrections (utile pour la partie « retour d'expérience »)

1. **Vainqueurs de tournois absents du texte Liquipedia** : ils sont calculés depuis les brackets, et une extraction naïve donne des résultats faux (ex. OWL 2018). Aucune question « qui a gagné X » n'est posée tant que les brackets ne sont pas parsés.
2. **Liquipedia** : `action=parse` est limité à une requête par 30 s, ce qui le rend inutilisable à grande échelle. Le texte est donc reconstruit depuis le wikitext.
3. **Générations lancées par erreur** depuis une autre session, puis tuées faute de RAM : ~415 chunks générés sur d'anciennes pages, régénérés automatiquement au refresh (reprise par `(id, revid)`).
4. **Critère RAFT** : 55 % des exemples sans oracle gardaient la réponse, parce que les entités de la réponse figuraient déjà dans la question. Le critère utilise désormais les éléments de la réponse absents de la question, en mots entiers.
5. **Fenêtre de contexte Ollama par défaut trop courte** pour 5 passages : `num_ctx = 8192` fixé dans le banc.
6. **Découpe des notes Blizzard** : les sections étaient fusionnées jusqu'à 250 mots, si bien que Genji se retrouvait dans un chunk intitulé « Tank > Domina » et que le RAG ratait S04 et S05. La découpe est maintenant faite par héros (42 chunks au lieu de 15) ; S04 et S05 sont retrouvées en position 1.
7. **Sauvegarde relue par `build-dataset`** : une copie du fichier de génération, laissée dans `data/qa/`, a injecté 57 anciennes paires Blizzard. Cela touche 8 exemples RAFT sur 14 250 (0,06 %) dans le jeu v1, celui de RAFT 4B. Le dataset et les exemples RAFT ont été reconstruits proprement le 13 oct. (v2) pour les runs suivants.
8. **VRAM non mesurée** pour les modèles créés avec `ollama create` (suffixe `:latest`) : corrigé, valeur mesurée a posteriori (3 873 Mo).

---

## 8. Limites et points à vérifier

- **Juge LLM non encore vérifié à la main** : `ow-bench review-export` (15 réponses par config), puis accord et kappa dans le rapport.
- **Biais de construction** : le test et l'index proviennent du même corpus, ce qui avantage les bras RAG face aux frontier sans RAG. Les questions temporelles et la Saison 5 montrent toutefois un vrai besoin d'information fraîche.
- **k différent** entre les bras : 4 pour les SLM, 5 pour le 14B et Sonnet.
- **Couverture « couvert / non couvert »** : heuristique, indicative.
- **Une seule graine**, pas d'intervalles de confiance : avec n = 219, ±2 à 3 points d'écart ne sont pas significatifs (l'écart RAFT / base, 3 points, est à la limite).
- **Mesures frontier** (latence, tok/s) indicatives : réseau et tokens de réflexion inclus.

## 9. Reste à faire

- [ ] RAFT Qwen3-1.7B (sur les exemples RAFT v2) → export → banc `slm-1.7b-raft-rag`
- [ ] SFT Qwen3-4B (2 epochs) → banc `slm-4b-sft`
- [ ] CPT puis CPT + SFT Qwen3-4B → banc `slm-4b-cpt-sft`
- [ ] Éventuellement : RAFT 4B v2 avec moins de refus (p_oracle 0,9), pour tester l'hypothèse de sur-abstention
- [ ] Vérification manuelle du juge ; mesure de la consommation électrique ; démo sur le Mac (GGUF)
- [ ] Rédaction ; citer Fandom et Liquipedia (CC-BY-SA, attribution) et Blizzard (notes de patch)

## 10. Attributions

- Overwatch Fandom wiki — contenu sous licence CC-BY-SA.
- Liquipedia Overwatch — contenu sous licence CC-BY-SA 3.0 (attribution obligatoire).
- Notes de patch officielles Overwatch — © Blizzard Entertainment, utilisées à des fins de recherche, source citée.
- Modèles : Qwen3 (Apache 2.0), GGUF Unsloth ; génération `qwen3.6:35b-a3b` (Apache 2.0).
