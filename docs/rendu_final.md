# OW-SLM — Dossier de rendu (résultats, coûts, complexité, historique)

Document de travail pour le rendu final de l'UE (échéance début novembre 2026). Il rassemble les chiffres mesurés,
les comparaisons entre approches, les coûts et la complexité de mise en œuvre, et l'historique du projet.
**État au 26 oct. 2026 : tous les entraînements et bancs sont faits.** Reste la vérification manuelle du juge (§8).

Sources des chiffres : `eval/report/report.md` (banc test), `eval/dev/report/report.md` (banc dev),
`eval/report/retrieval_hybrid.md` (recherche), `eval/report/training.md` (entraînements), `data/stats.json`,
`data/dataset/stats.json`, `data/dataset/raft_stats.json`, `data/dataset/raft_v2/augment_stats.json`,
journaux `data/qa/*.log`, `data/rag/v2_*.log`, `data/train/*.log`, historique git.

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
- Les notes Blizzard sont découpées finement, un chunk par héros, soit 42 chunks (voir §7.2, problème n°6).

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
- Beaucoup de questions sont **composées** (« X, et Y ? ») : elles demandent plusieurs faits dans une même réponse (voir §4.7).

### 2.3 Jeu de dev (17 oct., pour régler les variantes sans toucher au test)

- **327 questions** : 300 paires de **val** (au plus 2 par page), reformulées par `qwen3.6` pour ne pas recopier le passage,
  et 27 questions sans réponse générées (30 générées, 3 écartées et 3 corrigées à la main).
- Catégories : esport 163, lore 82, unanswerable 27, patch 25, maps_modes 20, gameplay 10.
- Commandes : `ow-bench --set dev run|judge|report`, sorties sous `eval/dev/`.
- **Limite constatée** : ses questions viennent des paires générées, donc à **un seul fait**. Il n'a pas détecté le
  défaut de réponses trop courtes du RAFT sur les questions composées du test (§4.7).

### 2.4 Données d'entraînement générées

- **Q/R LLM** : `qwen3.6:35b-a3b` en local (Ollama, licence Apache 2.0), 5 à 8 paires par chunk, ancrées dans le passage. Au total, 13 767 chunks générés, soit 100 482 paires brutes et 6,0 M tokens de sortie.
- **Q/R par templates**, sans LLM (infobox, joueurs, équipes, tournois, MVP) : 47 314 paires en moins de 2 s.
- **Filtrage** : 147 796 paires brutes donnent **107 271 paires finales** (102 160 en train, 5 111 en val, split par page). Les chunks sensibles (héros, patchs, Saison 5) sont inclus.

| Étape | Paires retirées |
|---|---|
| Périmées (revid) | 6 181 |
| Plafond tournois mineurs | 27 000 |
| Faible valeur (citations vocales, cosmétiques…) | 3 331 |
| Méta | 1 333 |
| Ancrage des nombres | 741 |
| Doublons exacts et flous | ~1 700 |
| Proximité avec le test | 224 |

- **CPT** : 12 360 chunks de texte brut, hors faible valeur (5,45 M tokens).
- **Couverture du test** : 164 faits sur 219 (heuristique) sont présents dans les données d'entraînement. Les résultats sont découpés en « couvert » / « non couvert ».

### 2.5 Exemples RAFT

Format : la question est accompagnée de k = 4 passages issus du vrai retriever hybride. Avec une probabilité p_oracle, ces passages comprennent le passage de réponse (l'**oracle**) et 3 distracteurs. Sinon, ce sont 4 distracteurs et la cible est un refus fixe (« je ne sais pas »). Tout distracteur qui pourrait contenir la réponse est écarté, pour que le refus soit justifié. La loss ne porte que sur la réponse, soit ~1,2 % des tokens. Les exemples font ~1 950 tokens en moyenne.

| Jeu | Utilisé par | p_oracle | Exemples (train) | Oracle | Refus | `answer_in_distractor` | Questions reformulées |
|---|---|---|---|---|---|---|---|
| **v1** (12 oct.) | RAFT 4B v1 | 0,8 | 14 250 | 11 446 | 2 691 | 113 | 0 |
| **v2** (17 oct.) | RAFT 4B v2, RAFT 1.7B | 0,9 | 14 072 | 12 839 | 1 172 | 61 | 6 524 (46 %) |

La v2 est construite à partir du diagnostic du RAFT v1 (§4.7) :
1. **Reformulation** de 50 % des questions non-refus par `qwen3.6`. Dans la v1, les questions recopiaient le passage oracle.
2. **Vérification des refus** par `qwen3.6` : 1 413 refus vérifiés. **178 refus faux ont été retirés** (163 où les passages contenaient bien la réponse, 15 partiels), soit ~13 %. 9 refus n'ont pas pu être vérifiés (sortie JSON tronquée) et sont gardés tels quels.
3. **p_oracle passé de 0,8 à 0,9**, donc moins de refus.

Un jeu « v1 reconstruit » (13 oct., après le problème n°7) existe aussi, mais il n'a servi à aucun entraînement.

---

## 3. Configurations comparées

| # | Configuration | Modèle | Contexte |
|---|---|---|---|
| 1 | SLM de base | Qwen3-1.7B / Qwen3-4B (GGUF Q4_K_M Unsloth) | question seule |
| 2 | SLM + SFT | Qwen3-4B + LoRA (102 k Q/R, 2 epochs) | question seule |
| 3 | SLM + CPT + SFT | Qwen3-4B + LoRA (texte brut 1 epoch, puis Q/R 2 epochs) | question seule |
| 4 | SLM + RAG | Qwen3-1.7B / 4B de base | 4 passages |
| 5 | **SLM + RAFT + RAG** | Qwen3-4B (v1 et v2), Qwen3-1.7B (v2) | 4 passages |
| 6 | LLM local | Qwen3-14B (Ollama) | ± 5 passages |
| 7 | Frontier | Claude Sonnet, Claude Opus (`claude -p`) | Sonnet ± 5 passages |

- **Évaluation** : un juge LLM (Claude Sonnet) note chaque réponse correct, partial, incorrect ou abstained ; pour les questions sans réponse, correct ou hallucinated. La référence fait foi. Score = correct + 0,5 × partial.
- La température vaut 0 et le mode thinking est désactivé pour les modèles Qwen.
- Tous les fine-tunings utilisent QLoRA (4 bits, r = 32, alpha = 32, 7 modules), exportés en GGUF Q4_K_M et servis par Ollama, comme les modèles de base.
- **Biais à signaler** :
  - les SLM + RAG utilisent k = 4, comme les exemples RAFT, alors que le 14B et Sonnet + RAG utilisent k = 5 ;
  - le test a été écrit à partir du même corpus que l'index RAG, ce qui favorise les bras RAG ;
  - le juge LLM est en cours de vérification manuelle (§8).

---

## 4. Résultats (jeu de test, 235 questions)

Bancs du 12-13 oct. (bases, frontier, RAFT v1) et du 17-18 oct. (RAFT v2, RAFT 1.7B, SFT, CPT + SFT).

### 4.1 Exactitude globale

| Configuration | Score % | Correct | Partiel | Incorrect | Abstention | Halluc. (/16) |
|---|---|---|---|---|---|---|
| Claude Opus | 56,0 | 120 | 23 | 21 | 71 | 0 |
| Claude Sonnet | 43,2 | 91 | 21 | 27 | 96 | 0 |
| **Claude Sonnet + RAG** (k=5) | **93,8** | 217 | 7 | 0 | 11 | 0 |
| Qwen3-14B | 12,6 | 21 | 17 | 170 | 17 | 10 |
| Qwen3-14B + RAG (k=5) | 90,6 | 207 | 12 | 7 | 9 | 0 |
| Qwen3-4B | 4,7 | 5 | 12 | 195 | 11 | 12 |
| Qwen3-4B + SFT | 11,5 | 18 | 18 | 182 | 1 | **16** |
| Qwen3-4B + CPT + SFT | 14,9 | 21 | 28 | 169 | 1 | **16** |
| **Qwen3-4B + RAG** (k=4) | **86,6** | 194 | 19 | 14 | 8 | 0 |
| Qwen3-4B RAFT v1 + RAG (k=4) | 83,6 | 187 | 19 | 9 | 20 | 0 |
| Qwen3-4B RAFT v2 + RAG (k=4) | 83,8 | 187 | 20 | 16 | 12 | 0 |
| Qwen3-1.7B | 2,3 | 3 | 5 | 203 | 10 | 14 |
| Qwen3-1.7B + RAG (k=4) | 80,9 | 183 | 14 | 31 | 4 | 3 |
| Qwen3-1.7B RAFT v2 + RAG (k=4) | 80,6 | 178 | 23 | 25 | 8 | **1** |

### 4.2 Par catégorie (score %)

| Configuration | lore | gameplay | esport | patch | maps | unanswerable |
|---|---|---|---|---|---|---|
| Claude Opus | 72,5 | 85,0 | 26,7 | 13,0 | 72,0 | 100 |
| Claude Sonnet | 57,8 | 69,0 | 12,8 | 4,0 | 56,0 | 100 |
| Claude Sonnet + RAG | 95,1 | 100 | 81,4 | 92,0 | 100 | 100 |
| Qwen3-14B | 18,6 | 9,0 | 2,3 | 8,0 | 18,0 | 37,5 |
| Qwen3-14B + RAG | 95,1 | 94,0 | 79,1 | 85,0 | 100 | 100 |
| Qwen3-4B | 2,9 | 3,0 | 3,5 | 1,0 | 8,0 | 25,0 |
| Qwen3-4B + SFT | 14,7 | 19,0 | 8,1 | 4,0 | 18,0 | 0 |
| Qwen3-4B + CPT + SFT | 18,6 | 26,0 | 7,0 | 6,0 | 26,0 | 0 |
| Qwen3-4B + RAG | 92,2 | 89,0 | 72,1 | 81,0 | 98,0 | 100 |
| Qwen3-4B RAFT v1 + RAG | 84,3 | 87,0 | 68,6 | 81,0 | 96,0 | 100 |
| Qwen3-4B RAFT v2 + RAG | 84,3 | 87,0 | 68,6 | 82,0 | 96,0 | 100 |
| Qwen3-1.7B | 0,0 | 1,0 | 3,5 | 0,0 | 6,0 | 12,5 |
| Qwen3-1.7B + RAG | 83,3 | 86,0 | 67,4 | 75,0 | 100 | 81,2 |
| Qwen3-1.7B RAFT v2 + RAG | 79,4 | 85,0 | 66,3 | 78,0 | 96,0 | 93,8 |

### 4.3 Questions temporelles et faits couverts (questions répondables, score %)

| Configuration | temporel (74) | non temporel (145) | couvert (164) | non couvert (55) |
|---|---|---|---|---|
| Claude Opus | 15,5 | 71,7 | 58,8 | 34,5 |
| Claude Sonnet | 5,4 | 56,2 | 46,6 | 16,4 |
| Claude Sonnet + RAG | 92,6 | 93,8 | 95,1 | 88,2 |
| Qwen3-14B + RAG | 87,2 | 91,4 | 91,8 | 84,5 |
| Qwen3-4B + SFT | 3,4 | 16,9 | 15,2 | 3,6 |
| Qwen3-4B + CPT + SFT | 6,8 | 20,7 | 18,3 | 9,1 |
| Qwen3-4B + RAG | 79,7 | 88,6 | 87,2 | 80,9 |
| Qwen3-4B RAFT v1 + RAG | 79,7 | 83,8 | 85,1 | 74,5 |
| Qwen3-4B RAFT v2 + RAG | 81,8 | 83,1 | 85,4 | 74,5 |
| Qwen3-1.7B + RAG | 75,0 | 83,8 | 82,0 | 77,3 |
| Qwen3-1.7B RAFT v2 + RAG | 77,7 | 80,7 | 81,4 | 74,5 |

Même sur les faits **couverts**, c'est-à-dire présents dans ses données d'entraînement, le SFT n'obtient que 15 % : il n'a pas mémorisé ce qu'il a vu.

### 4.4 Saison 5 (S01-S08, patch du 6 oct. 2026, absent de tout modèle pré-entraîné)

| Configuration | Correctes | Détail |
|---|---|---|
| Opus / Sonnet sans RAG | 0/8 | abstention (Opus : 1 erreur sur S02) |
| Sonnet + RAG, 14B + RAG | 7/8 | S08 en abstention |
| 4B + RAG | 5/8 + 1 partielle | S03 partielle, S04 incorrecte, S08 abstention |
| 4B RAFT v1 + RAG | 5/8 + 1 partielle | S03 partielle, S02 et S08 abstentions |
| **4B RAFT v2 + RAG** | **6/8 + 1 partielle** | S03 partielle, S08 abstention (corrige S04 et S02) |
| 1.7B + RAG | 6/8 | S06 et S08 incorrectes |
| **1.7B RAFT v2 + RAG** | **6/8 + 1 partielle** | S03 partielle, S08 abstention (au lieu d'une erreur) |
| 4B + SFT | 1/8 + 1 partielle | les notes Saison 5 sont pourtant dans ses données d'entraînement |
| 4B + CPT + SFT | 0/8 + 2 partielles | idem |

- S08 (mode Halloween) est raté partout à cause du retriever : le mot « Halloween » n'apparaît qu'une fois dans un passage de 457 mots, et les pages Fandom génériques passent devant. Nous l'avons laissé tel quel et le citons comme limite ; la question n'a pas été réécrite pour s'adapter au retriever.
- Sur ces faits vraiment nouveaux, **les RAFT v2 font mieux que leur modèle de base + RAG** et approchent le 14B et Sonnet + RAG.

### 4.5 Performance d'inférence (RTX 5070 Ti, Ollama, Q4_K_M)

| Configuration | Latence p50 (s) | p95 (s) | TTFT p50 (s) | tok/s | VRAM (Go) | Coût / requête |
|---|---|---|---|---|---|---|
| Claude Opus | 5,78 | 11,65 | 2,62 | ~200* | — | 0,0148 $ (équiv. API) |
| Claude Sonnet | 5,62 | 11,52 | 3,25 | ~390* | — | 0,0084 $ |
| Claude Sonnet + RAG | 3,14 | 5,11 | 1,69 | ~264* | — | 0,0203 $ |
| Qwen3-14B + RAG | 1,24 | 1,89 | 0,87 | 75 | 10,5 | 0 (local) |
| Qwen3-4B + SFT | 0,12 | 0,20 | 0,03 | 227 | 3,9 | 0 |
| Qwen3-4B + RAG | 0,46 | 0,78 | 0,29 | 193 | 3,9 | 0 |
| Qwen3-4B RAFT v2 + RAG | 0,37 | 0,51 | 0,27 | 207 | 3,9 | 0 |
| Qwen3-1.7B + RAG | 0,24 | 0,39 | 0,16 | 362 | 2,2 | 0 |
| Qwen3-1.7B RAFT v2 + RAG | 0,21 | 0,28 | 0,15 | 383 | 2,2 | 0 |

\* Pour `claude -p`, les débits et latences sont indicatifs : ils incluent le réseau et les tokens de réflexion. Le prompt RAG fait ~2 100 tokens pour les Qwen (k=4) et ~4 800 pour Sonnet (k=5).

**Longueur des réponses** : 25 mots en moyenne pour le 4B + RAG (29 tokens médians), 14,5 mots pour les RAFT (21 tokens). C'est l'une des causes de l'écart de score (§4.7).

### 4.6 Ce que montrent les résultats

1. **Le RAG fait l'essentiel du gain**, quelle que soit la taille :
   - le 4B passe de 4,7 % à 86,6 % ;
   - le 1.7B passe de 2,3 % à 80,9 % ;
   - le 14B passe de 12,6 % à 90,6 %.
   Sans RAG, tous les modèles locaux hallucinent massivement : 62 à 88 % sur les questions sans réponse.
2. **Le fine-tuning seul (SFT, CPT + SFT) ne suffit pas** : 11,5 % et 14,9 %, contre 4,7 % pour le modèle de base.
   - Même sur les faits **couverts** par ses données, le SFT n'obtient que 15 %, et 1/8 sur la Saison 5 alors qu'il l'a vue à l'entraînement.
   - Les deux modèles **hallucinent sur les 16 questions sans réponse** et ne s'abstiennent presque jamais (1 fois sur 219) : entraînés uniquement à répondre, ils ont désappris le « je ne sais pas ».
   - Le CPT apporte un gain modeste (+3,4 points), comme attendu.
   - Ces deux bras confirment les limites du SFT annoncées dans le cadrage : mémorisation faible d'un petit modèle, hallucination assurée hors corpus.
3. **Un SLM de 4B avec RAG se place à 7 points de Sonnet + RAG et à 4 points du 14B + RAG**, pour un coût marginal nul. Il est ~7 fois plus rapide que Sonnet + RAG et ~2,7 fois plus rapide que le 14B, avec 2,7 fois moins de VRAM. Il tient sur un portable (démo Mac).
4. **Les frontier sans RAG ne connaissent pas l'actualité du domaine.** Ils obtiennent 5 à 16 % sur les questions temporelles et 0/8 sur la Saison 5. En revanche, ils s'abstiennent au lieu d'halluciner (0 % d'hallucination, 32 à 44 % d'abstention).
5. **Le RAFT ne bat pas le modèle de base + RAG en score global, mais il change le comportement** :
   - 4B : 83,8 % (v2) contre 86,6 %, soit un écart à la limite de la significativité (§8) ;
   - 1.7B : 80,6 % contre 80,9 %, égalité ;
   - **hallucinations du 1.7B divisées par trois** (1 sur 16 au lieu de 3) : c'est le cas visé par RAFT, un très petit modèle qui lit mal des passages bruités ;
   - **meilleur sur la Saison 5** (6/8 + 1 partielle pour les deux RAFT v2), là où l'information est vraiment nouvelle ;
   - réponses plus courtes, latence p95 plus basse (0,51 s contre 0,78 s).

### 4.7 Diagnostic du RAFT et RAFT v2

**RAFT v1 (13 oct.)** : 83,6 %, avec 20 abstentions contre 8 pour le 4B de base. Diagnostic sur `raft_val` (même distribution que l'entraînement) :
- sur les exemples avec oracle, le RAFT ne refuse que dans 3 % des cas (base : 2 %) ; la sur-abstention n'apparaît que sur le test ;
- cause : les questions d'entraînement recopiaient la formulation du passage oracle. Face aux questions du test, formulées autrement, le modèle ne reconnaît plus le passage et refuse ;
- ~12 % des étiquettes « refus » étaient fausses, la réponse étant en fait dans les passages ;
- une partie des réussites du modèle de base vient de sa mémoire paramétrique (G41, G43) et non des passages.

**RAFT v2 (17 oct.)** : reformulations, refus vérifiés, p_oracle 0,9 (§2.5). Le choix a été fait sur le jeu de dev :

| Jeu de dev (327 q.) | Score % | Abstention | Halluc. |
|---|---|---|---|
| Qwen3-4B + RAG | 83,3 | 18 | 0 |
| Qwen3-4B RAFT v1 + RAG | 80,3 | 40 | 0 |
| **Qwen3-4B RAFT v2 + RAG** | **87,2** | 15 | 0 |
| Qwen3-1.7B RAFT v2 + RAG | 83,8 | 13 | 0 |

**Sur le test, le gain ne se transfère qu'en partie** : 83,8 % contre 83,6 % pour la v1, avec des abstentions passées de 20 à 12, mais toujours sous le 4B de base (86,6 %). Comparaison question par question avec le 4B de base : le RAFT v2 gagne 8 questions (S04, T30, G45, E09…) et en perd 19 :
- **réponses incomplètes sur les questions composées** : la majorité des pertes sont des « partielles » (E21, L41, L45, L48, M14…). Les exemples RAFT ne contiennent que des paires à un seul fait, et le modèle a appris à ne donner qu'un fait ;
- **quelques refus restants** alors que la réponse est dans les passages (G41, G43, T14).

Le jeu de dev n'a pas vu ce défaut, faute de questions composées. **Une v3 n'a pas été entraînée** : ses corrections auraient été conçues à partir des erreurs du test, ce qui revient à régler le système sur le test (§8). Elle figure dans les perspectives (§9).

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
| Données RAFT v2 : vérification des refus + reformulations | ~50 min (1 426 refus, ~2 s/ex) + ~1 h 15 (6 864 questions, 1,5 ex/s) | GPU (`qwen3.6`) |
| Jeu de dev (300 reformulations + 30 sans réponse) | quelques minutes | GPU |
| Export GGUF Q4_K_M | 1 min (1.7B, 1,1 Go) à 3 min (4B, 2,5 Go) ; 7 min la première fois (compilation de llama.cpp) | CPU / GPU |
| Banc local (235 q.) | 1 à 5 min par configuration | GPU |
| Banc frontier (235 q.) | ~24 min par config sans RAG, ~14 min avec RAG | abonnement |
| Jugement (235 q.) | ~1,5 min par config (lots de 15, ~5 s/lot) | abonnement |

**Entraînements QLoRA** (RTX 5070 Ti sous WSL2, `eval/report/training.md`) :

| Run | Exemples | Pas | Durée | s/ex | tok/s | Pic VRAM (Go) | Loss train / val |
|---|---|---|---|---|---|---|---|
| RAFT 4B v1 | 14 250 | 891 | 3 h 22 | 0,85 | 2 322 | 13,9 | 0,246 / 0,240 |
| RAFT 4B v2 | 14 072 | 880 | 3 h 29 | 0,89 | 2 218 | 13,8 | 0,278 / 0,275 |
| RAFT 1.7B v2 | 14 072 | 880 | 1 h 15 | 0,32 | 6 198 | 11,5 | 0,346 / 0,337 |
| SFT 4B (2 epochs, packing) | 102 160 | 350 | 2 h 05 | 0,036 | 3 007 | 16,1** | 1,029 / 1,068 |
| CPT 4B (1 epoch) | 12 360 | 84 | 30 min | 0,15 | 3 013 | 6,8 | 2,169 / — |
| CPT + SFT 4B | 102 160 | 350 | 2 h 04 | 0,036 | 3 032 | 16,1** | 1,012 / 1,059 |

\** Go = 10⁹ octets (`torch.cuda.max_memory_allocated`), soit 15,0 Gio : la limite de la carte est presque atteinte.
Les losses RAFT ne portent que sur ~20 tokens de réponse par exemple ; celles du SFT, sur des réponses plus longues et sans passage. Elles ne sont pas comparables entre étapes.
Le RAFT v2 a été ralenti ~25 min par une autre application qui utilisait le GPU.

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
  - 0,2 à 0,4 s par réponse avec RAG ;
  - 2,2 à 3,9 Go de VRAM, possible sur un portable.
- **Frontier** : 0,008 à 0,02 $ par requête en équivalent API, 3 à 6 s de latence, dépendance au réseau et au fournisseur. Ordre de grandeur pour 10 000 requêtes par jour avec Sonnet + RAG : ~200 $ par jour.

### 5.3 Coût de mise à jour (Saison 5, sortie le 6 oct. 2026)

| Étape | Mesure |
|---|---|
| Détection des pages modifiées (comparaison des revid) | Fandom : 52 modifiées + 1 nouvelle ; Liquipedia : 167 modifiées + 9 nouvelles |
| Délai des wikis | Fandom partiel au bout de 5 jours (Ana, Shion, Eichenwalde non mis à jour) ; Liquipedia crée ses pages de patch par lots, avec **2 à 4 semaines de retard** → ajout des notes officielles Blizzard (scraper dédié, une page HTML par mois, exécution en quelques secondes) |
| Régénération Q/R | 839 chunks en 1 h 32 (6 544 paires), puis 42 chunks Blizzard en ~5 min (249 paires) |
| **Mise à jour de l'index RAG** | **~6 s** (107 textes encodés, le reste repris du cache sha1), puis 3 s après la redécoupe Blizzard |
| Réentraînement | RAFT 4B : ~3 h 30 ; RAFT 1.7B : 1 h 15 ; SFT 4B : 2 h 05 (+ 30 min de CPT) |

**Lecture.** Pour un bras RAG, la mise à jour coûte quelques secondes de réindexation, et le modèle répond aussitôt sur la Saison 5 (6 à 7 questions sur 8). Un bras SFT, lui, exige de régénérer les Q/R puis de réentraîner, soit plusieurs heures de GPU à chaque patch, pour un résultat médiocre (1/8 sur la Saison 5). Un RAFT n'a pas besoin d'être réentraîné à chaque patch : il a appris à lire des passages, pas les faits eux-mêmes. Un frontier attend la prochaine version du modèle.

---

## 6. Complexité de mise en œuvre

### 6.1 Par approche

| Approche | Composants nécessaires | Effort de développement | Calcul initial | Mise à jour | Risque principal |
|---|---|---|---|---|---|
| SLM de base | Ollama | nul | nul | impossible | hallucination massive (75-88 %) |
| SLM + RAG | corpus, découpe, index BM25 + embeddings, retriever | moyen (`rag/` ~600 lignes hors RAFT) | ~6 min d'embeddings | secondes | dépend du retriever (S08) |
| SLM + SFT | corpus, génération Q/R, filtrage, QLoRA | élevé (`gen/` 1 169 lignes + `train/` 375) | ~26 h de génération + 2 h d'entraînement | heures (génération + entraînement) | mémorisation faible (15 % sur les faits couverts), hallucination 100 % |
| SLM + CPT + SFT | idem + passe de texte brut | élevé | + 30 min | heures | gain modeste mesuré (+3,4 points) |
| **SLM + RAFT + RAG** | tout ce qui précède + construction des exemples RAFT | le plus élevé | génération + 7 min + 1 h 15 à 3 h 30 (+ ~2 h pour la v2) | secondes (index), réentraînement optionnel | réponses trop courtes, abstentions résiduelles |
| LLM local 14B + RAG | RAG + GPU 12 Go ou plus | moyen | idem RAG | secondes | latence ×2,7, VRAM ×2,7 |
| Frontier (+ RAG) | abonnement / API (+ RAG) | faible | nul | dépend du fournisseur | coût récurrent, données envoyées à un tiers, connaissances datées sans RAG |

### 6.2 Taille du code (Python)

| Package | Rôle | Fichiers | Lignes |
|---|---|---|---|
| `scraper/` | collecte, nettoyage, découpe, refresh, Blizzard | 12 | 1 021 |
| `gen/` | génération Q/R, templates, dataset | 4 | 1 169 |
| `rag/` | BM25, embeddings, retriever hybride, RAFT, RAFT v2 et jeu de dev (`augment.py`) | 10 | 1 055 |
| `bench/` | banc, backends, juge, rapport, jeu de dev | 8 | 908 |
| `train/` | QLoRA SFT/CPT/RAFT, export GGUF | 6 | 375 |
| **Total** | | 40 | **~4 530** |

### 6.3 Contraintes d'environnement rencontrées

- **Smart App Control** (Windows) bloque les `.exe` des venv, `uv run` et `uv sync`. Contournement : interpréteur de base uv avec `PYTHONPATH` vers les paquets du venv.
- **Fine-tuning sous WSL2** (Ubuntu 24.04) : Unsloth et bitsandbytes s'utilisent mal sous Windows, et le GPU Blackwell exige CUDA ≥ 12.8.
- **Mémoire** : le modèle de génération occupe ~16 Go de RAM, WSL jusqu'à 15 Go pendant un entraînement, et les tâches de fond longues sont tuées si la RAM manque. Tous les traitements longs sont donc lancés en processus indépendants et sont **reprenables** (append JSONL, fichiers STOP, `--resume`). Les entraînements de la nuit du 17 oct. ont tourné en une chaîne unique (script `.bat`, fichier d'état), sans surveillance.
- **VRAM de 16 Go partagée** entre Ollama (génération, embeddings, banc) et l'entraînement : il faut décharger les modèles avant chaque entraînement (pic SFT 4B avec packing : 15,0 Gio).

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
| 12-13 oct. | **Premier entraînement complet : RAFT Qwen3-4B v1** (3 h 22), export, banc : 83,6 %, sous le 4B + RAG | `aa00b41`, `1786de9` |
| 17 oct. | Diagnostic de la sur-abstention ; jeu de dev ; données RAFT v2 (reformulations, refus vérifiés) ; RAFT 4B v2 : 87,2 % sur le dev, 83,8 % sur le test | `e0fb730` → `f59dc5c` |
| 17-18 oct. (nuit) | RAFT 1.7B v2, SFT 4B, CPT 4B, CPT + SFT 4B, exports et bancs, en chaîne unique | `800741f`, `d97d5c2` |
| 26 oct. | Mise à jour du dossier, échantillon de vérification manuelle du juge, préparation de la soutenance | |

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
| Jeu de dev séparé pour régler le RAFT v2 | ne plus utiliser le test pour choisir entre variantes |
| Pas de RAFT v3 | ses corrections viendraient de l'analyse des erreurs du test ; à une semaine de l'échéance, le gain attendu (2 à 3 points, au mieux l'égalité) ne justifie ni ce biais ni ~6 h de calcul |

### 7.2 Problèmes rencontrés et corrections (utile pour la partie « retour d'expérience »)

1. **Vainqueurs de tournois absents du texte Liquipedia** : ils sont calculés depuis les brackets, et une extraction naïve donne des résultats faux (ex. OWL 2018). Aucune question « qui a gagné X » n'est posée tant que les brackets ne sont pas parsés.
2. **Liquipedia** : `action=parse` est limité à une requête par 30 s, ce qui le rend inutilisable à grande échelle. Le texte est donc reconstruit depuis le wikitext.
3. **Générations lancées par erreur** depuis une autre session, puis tuées faute de RAM : ~415 chunks générés sur d'anciennes pages, régénérés automatiquement au refresh (reprise par `(id, revid)`).
4. **Critère RAFT** : 55 % des exemples sans oracle gardaient la réponse, parce que les entités de la réponse figuraient déjà dans la question. Le critère utilise désormais les éléments de la réponse absents de la question, en mots entiers.
5. **Fenêtre de contexte Ollama par défaut trop courte** pour 5 passages : `num_ctx = 8192` fixé dans le banc.
6. **Découpe des notes Blizzard** : les sections étaient fusionnées jusqu'à 250 mots, si bien que Genji se retrouvait dans un chunk intitulé « Tank > Domina » et que le RAG ratait S04 et S05. La découpe est maintenant faite par héros (42 chunks au lieu de 15) ; S04 et S05 sont retrouvées en position 1.
7. **Sauvegarde relue par `build-dataset`** : une copie du fichier de génération, laissée dans `data/qa/`, a injecté 57 anciennes paires Blizzard. Cela touche 8 exemples RAFT sur 14 250 (0,06 %) dans le jeu v1, celui de RAFT 4B v1. Le dataset a été reconstruit proprement le 13 oct. ; tous les entraînements suivants en dérivent.
8. **VRAM non mesurée** pour les modèles créés avec `ollama create` (suffixe `:latest`) : corrigé, valeur mesurée a posteriori (3 873 Mo).
9. **Sur-abstention du RAFT v1** : les questions d'entraînement recopiaient le passage oracle, et ~12 % des refus étaient faux. Corrigé dans la v2 (§4.7).
10. **Jeu de dev trop facile** : il ne contient que des questions à un seul fait, si bien que le gain du RAFT v2 (+3,9 points sur le dev) ne s'est pas retrouvé sur le test. Leçon : un jeu de dev doit reproduire la forme des questions du test, pas seulement leur thème.

---

## 8. Limites et points à vérifier

- **Juge LLM en cours de vérification manuelle** : 112 verdicts (8 par configuration, stratifiés par verdict : les abstentions et hallucinations y sont surreprésentées) dans `eval/review/sample.csv`. L'accord et le kappa s'afficheront dans le rapport.
- **Biais de construction** : le test et l'index proviennent du même corpus, ce qui avantage les bras RAG face aux frontier sans RAG. Les questions temporelles et la Saison 5 montrent toutefois un vrai besoin d'information fraîche.
- **Le test a été consulté pour le diagnostic du RAFT** (v1 puis v2) : les écarts observés dessus servent d'explication, pas de réglage. C'est pour cette raison qu'il n'y a pas eu de v3.
- **k différent** entre les bras : 4 pour les SLM, 5 pour le 14B et Sonnet.
- **Couverture « couvert / non couvert »** : heuristique, indicative.
- **Une seule graine**, pas d'intervalles de confiance : avec n = 219, ±2 à 3 points d'écart ne sont pas significatifs. Les écarts RAFT / base (2,8 points en 4B, 0,3 en 1.7B) sont dans cette marge ; l'écart d'hallucination du 1.7B (1 contre 3 sur 16) porte sur de très petits effectifs.
- **Mesures frontier** (latence, tok/s) indicatives : réseau et tokens de réflexion inclus.

## 9. Reste à faire et perspectives

Reste à faire :
- [ ] Vérification manuelle du juge (`eval/review/sample.csv`, colonne `human_verdict`), puis `ow-bench report`
- [ ] Mesure de la consommation électrique (`nvidia-smi --query-gpu=power.draw`) pendant un banc
- [ ] Démo sur le Mac (GGUF RAFT 1.7B ou 4B + index RAG)
- [ ] Présentation de soutenance ; citer Fandom et Liquipedia (CC-BY-SA, attribution) et Blizzard (notes de patch)

Perspectives (non réalisées) :
- **RAFT v3** : exemples à questions composées (deux paires du même passage fusionnées, réponse complète), réponses cibles en phrases complètes, et un jeu de dev qui contienne aussi des questions composées.
- Plusieurs graines et intervalles de confiance (bootstrap) pour les écarts de quelques points.
- Parser les brackets Liquipedia pour poser des questions « qui a gagné X ».
- Améliorer le retriever sur les passages longs (S08) : découpe plus fine ou reranker.

## 10. Attributions

- Overwatch Fandom wiki — contenu sous licence CC-BY-SA.
- Liquipedia Overwatch — contenu sous licence CC-BY-SA 3.0 (attribution obligatoire).
- Notes de patch officielles Overwatch — © Blizzard Entertainment, utilisées à des fins de recherche, source citée.
- Modèles : Qwen3 (Apache 2.0), GGUF Unsloth ; génération `qwen3.6:35b-a3b` (Apache 2.0).
