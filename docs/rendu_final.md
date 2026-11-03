# OW-SLM — Dossier de rendu (résultats, coûts, complexité, historique)

Document de travail pour le rendu final de l'UE (échéance début novembre 2026). Il rassemble les chiffres mesurés,
les comparaisons entre approches, les coûts et la complexité de mise en œuvre, et l'historique du projet.
**État au 29 oct. 2026 : tous les entraînements et bancs sont faits** (RAFT v1 à v4, normalisation des questions, jeu joueurs).
Résumé en une ligne : le meilleur SLM est le **Qwen3-4B de base + RAG** (86,6 à 87,9 % sur le test selon l'exécution), au niveau de
Claude Sonnet + RAG sur de vraies questions de joueurs ; aucun des quatre RAFT ne le bat (§4.12).

Sources des chiffres : `eval/report/report.md` (banc test), `eval/dev/report/report.md` (banc dev), `eval/player/report/report.md` (jeu joueurs),
`eval/report/retrieval_hybrid.md` (recherche), `eval/report/training.md` (entraînements), `data/stats.json`,
`data/dataset/stats.json`, `data/dataset/raft_stats.json`, `data/dataset/raft_v{2,3,4}/augment_stats.json`, `eval/report/error_sources.md`,
journaux `data/qa/*.log`, `data/rag/v2_*.log`, `data/train/*.log`, historique git.

---

## 1. Objectif et question posée

Montrer dans quels cas un **petit modèle de langage (SLM, 1,7-4 B paramètres)** est pertinent face aux LLM locaux
plus gros (14 B) et aux modèles frontier (Claude Sonnet / Opus), sur un domaine de niche qui évolue vite :
**Overwatch** (lore, gameplay, patchs, esport). Les critères comparés sont l'exactitude, l'hallucination,
la latence, la mémoire, le coût par requête, le coût de construction et le coût de mise à jour.

Configuration principale visée au départ : **SLM + RAG + RAFT** (fine-tuning au format RAG). Après quatre versions du RAFT,
la meilleure configuration mesurée est finalement le SLM de base + RAG, avec une normalisation de la question pour les saisies de joueurs (§4.12).

---

## 2. Données

Trois jeux de questions servent à l'évaluation, chacun avec un rôle : le **test** (mesure finale, §2.2), le **dev**
(choisir entre variantes sans toucher au test, §2.3) et le **jeu joueurs** (vraies saisies de joueurs, usage réel, §2.4).
Les trois sont notés par le même juge (Claude Sonnet, §3).

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
- Toute paire d'entraînement trop proche d'une question du test est supprimée : 223 paires retirées.
- Beaucoup de questions sont **composées** (« X, et Y ? ») : elles demandent plusieurs faits dans une même réponse (voir §4.7).

### 2.3 Jeu de dev (17 oct., pour régler les variantes sans toucher au test)

- **327 questions** : 300 paires de **val** (au plus 2 par page), reformulées par `qwen3.6` pour ne pas recopier le passage,
  et 27 questions sans réponse générées (30 générées, 3 écartées et 3 corrigées à la main).
- Catégories : esport 163, lore 82, unanswerable 27, patch 25, maps_modes 20, gameplay 10.
- Commandes : `ow-bench --set dev run|judge|report`, sorties sous `eval/dev/`.
- **Limite constatée** : ses questions viennent des paires générées, donc à **un seul fait**. Il n'a pas détecté le
  défaut de réponses trop courtes du RAFT sur les questions composées du test (§4.7).
- **Limite plus large, constatée avec les RAFT v3 et v4** : il est généré comme les données d'entraînement du RAFT (mêmes paires,
  reformulées par le même LLM), donc il les favorise. Les RAFT y gagnent 2 à 5 points sur le modèle de base, gain qui ne se
  retrouve ni sur le test ni sur le jeu joueurs (§4.12).

### 2.4 Jeu joueurs (27-29 oct., usage réel)

- **40 questions tapées par de vrais joueurs** (`eval/player_set.jsonl`), telles quelles : fautes de noms (« Gesnji ultimate ability »),
  mots-clés sans verbe (« Mercy flash heal cooldown »), jargon (« C9 », « rez », « Bap », « hitscan »), questions de liste.
  Chaque question garde aussi une version propre (`question_clean`) et la source de la réponse dans le corpus.
- Deux lots : **J01-J15** (27 oct.), qui ont servi à mettre au point la normalisation des questions (§4.10), et **J16-J40** (29 oct.),
  ajoutés ensuite et jamais utilisés pour régler quoi que ce soit.
- Types (`kind`) : fiche 16, jargon 7, valeur 6, liste 5, combinée 4, avis 2. Catégories : gameplay 22, lore 13, patch 2, esport 1,
  cartes 1, sans réponse 1. Deux questions (J28, J29 : types de compositions d'équipe) sont absentes du corpus.
- Références trouvées dans le corpus et validées par l'utilisateur, sauf J08, J10, J18 et J22, encore à valider (§8).
- Avec 40 questions, une question vaut 2,5 points : le jeu sert à voir des tendances et des types d'échec, pas à départager à 2 points près.
- Commandes : `ow-bench --set player run|judge|report`, sorties sous `eval/player/`.

### 2.5 Données d'entraînement générées

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
| Proximité avec le test | 223 |

- **CPT** : 12 360 chunks de texte brut, hors faible valeur (5,45 M tokens).
- **Couverture du test** : 164 faits sur 219 (heuristique) sont présents dans les données d'entraînement. Les résultats sont découpés en « couvert » / « non couvert ».

### 2.6 Exemples RAFT

Format : la question est accompagnée de k = 4 passages issus du vrai retriever hybride. Avec une probabilité p_oracle, ces passages comprennent le passage de réponse (l'**oracle**) et 3 distracteurs. Sinon, ce sont 4 distracteurs et la cible est un refus fixe (« je ne sais pas »). Tout distracteur qui pourrait contenir la réponse est écarté, pour que le refus soit justifié. La loss ne porte que sur la réponse, soit ~1,2 % des tokens. Les exemples font ~1 950 tokens en moyenne.

| Jeu | Utilisé par | p_oracle | Exemples (train) | Oracle | Refus | `answer_in_distractor` | Questions reformulées |
|---|---|---|---|---|---|---|---|
| **v1** (12 oct.) | RAFT 4B v1 | 0,8 | 14 250 | 11 446 | 2 691 | 113 | 0 |
| **v2** (17 oct.) | RAFT 4B v2, RAFT 1.7B | 0,9 | 14 072 | 12 839 | 1 172 | 61 | 6 524 (46 %) |
| **v3** (27-28 oct.) | RAFT 4B v3 | (v2) | 14 072 | (v2) | (v2) | (v2) | v2 + 3 703 composées + 1 371 bruitées |
| **v4** (29 oct.) | RAFT 4B v4 | — | 2 650 (1 325 nouveaux + 1 325 de v2) | 86 % des nouveaux | 112 (nouveaux) | — | 453 au registre « joueur » |

La v2 est construite à partir du diagnostic du RAFT v1 (§4.7) :
1. **Reformulation** de 50 % des questions non-refus par `qwen3.6`. Dans la v1, les questions recopiaient le passage oracle.
2. **Vérification des refus** par `qwen3.6` : 1 413 refus vérifiés. **178 refus faux ont été retirés** (163 où les passages contenaient bien la réponse, 15 partiels), soit ~13 %. 9 refus n'ont pas pu être vérifiés (sortie JSON tronquée) et sont gardés tels quels.
3. **p_oracle passé de 0,8 à 0,9**, donc moins de refus.

Un jeu « v1 reconstruit » (13 oct., après le problème n°7) existe aussi, mais il n'a servi à aucun entraînement.

La **v3** part de la v2 (mêmes passages) et vise les défauts vus sur le dev et le jeu joueurs, jamais sur le test (§4.7) :
1. **Questions composées** (`augment compose`, `qwen3.6`) : pour 30 % des oracles, une 2ᵉ paire du même chunk est fusionnée en une question
   à deux faits, avec une réponse complète (3 703 exemples). Longueur moyenne des réponses d'entraînement : 15,8 → 20,7 mots.
2. **Saisies bruitées** (`augment apply3`, sans LLM) : 15 % des questions dégradées comme un joueur les taperait (fautes, mots-clés, sans « ? »), 1 371 exemples.

La **v4** (`augment hard | teach | apply4`) est une **distillation de la lecture du 35B** :
1. `hard` : à partir de 3 000 chunks graines (héros 30 %, patchs 30 %, cartes 20 %, esport 20 %) et de 2 passages liés, `qwen3.6` écrit une question
   difficile d'un type imposé (conditionnelle, valeur actuelle entre patchs, liste, croisement de passages, comparaison), au registre normal ou
   « joueur ». 2 276 acceptées ; rejets : non autonome 354, impossible 128, sources invalides 89, autres 33 ; filtre de proximité avec les trois jeux de questions.
2. `teach` : chaque question passe par le vrai retriever (k = 4) et le prompt de l'éval ; le 35B répond (consigne : phrase directe d'une à trois
   phrases, sans markdown), puis un 2ᵉ appel compare à la référence : 1 289 accords, 211 partiels, 537 désaccords, 215 refus du professeur, 4 tronqués.
   Gardés : les accords (cible = réponse du 35B) et les refus justifiés (oracle absent des passages), soit 1 406.
3. `apply4` : 1 325 nouveaux exemples mélangés à autant d'exemples v2 ; réponses de 29 mots en moyenne ; oracle dans les passages pour 86 % des exemples.

---

## 3. Configurations comparées

| # | Configuration | Modèle | Contexte |
|---|---|---|---|
| 1 | SLM de base | Qwen3-1.7B / Qwen3-4B (GGUF Q4_K_M Unsloth) | question seule |
| 2 | SLM + SFT | Qwen3-4B + LoRA (102 k Q/R, 2 epochs) | question seule |
| 3 | SLM + CPT + SFT | Qwen3-4B + LoRA (texte brut 1 epoch, puis Q/R 2 epochs) | question seule |
| 4 | SLM + RAG | Qwen3-1.7B / 4B de base | 4 passages |
| 5 | **SLM + RAFT + RAG** | Qwen3-4B (v1 à v4), Qwen3-1.7B (v2) | 4 passages (6 pour la variante v2 k6) |
| 5b | SLM (+ RAFT) + RAG + **normalisation** | Qwen3-4B de base, RAFT v2/v3/v4 | question corrigée puis reformulée si besoin (§4.10) |
| 6 | LLM local | Qwen3-14B (Ollama) | ± 5 passages |
| 7 | Frontier | Claude Sonnet, Claude Opus (`claude -p`) | Sonnet ± 5 passages |
| 8 | Frontier + recherche web | Claude Sonnet + outil WebSearch | recherche web libre (74 questions temporelles seulement, §5.2) |

- **Évaluation** : un juge LLM (Claude Sonnet) note chaque réponse correct, partial, incorrect ou abstained ; pour les questions sans réponse, correct ou hallucinated. La référence fait foi. Score = correct + 0,5 × partial.
- La température vaut 0 et le mode thinking est désactivé pour les modèles Qwen.
- Tous les fine-tunings utilisent QLoRA (4 bits, r = 32, alpha = 32, 7 modules), exportés en GGUF Q4_K_M et servis par Ollama, comme les modèles de base.
- **Biais à signaler** :
  - les SLM + RAG utilisent k = 4, comme les exemples RAFT, alors que le 14B et Sonnet + RAG utilisent k = 5 ;
  - le test a été écrit à partir du même corpus que l'index RAG, ce qui favorise les bras RAG ;
  - le juge LLM a été vérifié à la main (§8).
- **Jeux passés** : test pour toutes les configurations ; dev pour les variantes des SLM + RAG ; jeu joueurs pour les meilleurs SLM, le 14B + RAG et Sonnet + RAG.

---

## 4. Résultats (jeu de test, puis dev, jeu joueurs et synthèse)

Bancs du 12-13 oct. (bases, frontier, RAFT v1), du 17-18 oct. (RAFT v2, RAFT 1.7B, SFT, CPT + SFT) et du 29 oct. (RAFT v3, v4, v2 k6, 4B + normalisation).

**À lire avec §4.11** : sur le test, la normalisation ne modifie que 2 questions sur 235. La ligne « 4B + RAG + normalisation » est donc, en pratique,
une 2ᵉ exécution du 4B + RAG (29 oct. contre 12 oct.) : l'écart de 1,3 point entre les deux est du bruit d'exécution, pas un effet de la normalisation.

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
| Qwen3-4B RAFT v2 + RAG (k=6) | 84,0 | 183 | 29 | 10 | 12 | 1 |
| Qwen3-4B RAFT v3 + RAG (k=4) | 84,7 | 187 | 24 | 14 | 10 | 0 |
| Qwen3-4B RAFT v4 + RAG (k=4) | 85,3 | 191 | 19 | 16 | 9 | 0 |
| Qwen3-4B + RAG + normalisation (2ᵉ exécution) | 87,9 | 199 | 15 | 11 | 10 | 0 |
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
| Qwen3-4B RAFT v3 + RAG | 88,2 | 87,0 | 67,4 | 82,0 | 98,0 | 100 |
| Qwen3-4B RAFT v4 + RAG | 85,3 | 88,0 | 76,7 | 79,0 | 98,0 | 100 |
| Qwen3-4B + RAG + normalisation | 92,2 | 88,0 | 74,4 | 85,0 | 100 | 100 |
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
| Qwen3-4B RAFT v3 + RAG | 80,4 | 85,2 | 86,6 | 74,5 |
| Qwen3-4B RAFT v4 + RAG | 79,1 | 86,9 | 85,1 | 81,8 |
| Qwen3-4B + RAG + normalisation | 83,1 | 89,0 | 87,8 | 84,5 |
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
| 4B RAFT v3 + RAG | 7/8 | S08 abstention (S03 complète : questions composées) |
| 4B RAFT v4 + RAG | 6/8 + 1 partielle | S03 partielle, S08 abstention |
| 4B + RAG, 2ᵉ exécution (normalisation) | 6/8 + 1 partielle | S03 partielle, S08 abstention (S04 correcte cette fois) |
| 1.7B + RAG | 6/8 | S06 et S08 incorrectes |
| **1.7B RAFT v2 + RAG** | **6/8 + 1 partielle** | S03 partielle, S08 abstention (au lieu d'une erreur) |
| 4B + SFT | 1/8 + 1 partielle | les notes Saison 5 sont pourtant dans ses données d'entraînement |
| 4B + CPT + SFT | 0/8 + 2 partielles | idem |

- S08 (mode Halloween) est raté partout à cause du retriever : le mot « Halloween » n'apparaît qu'une fois dans un passage de 457 mots, et les pages Fandom génériques passent devant. Nous l'avons laissé tel quel et le citons comme limite ; la question n'a pas été réécrite pour s'adapter au retriever.
- Sur ces faits vraiment nouveaux, les RAFT v2 et v3 font un peu mieux que la 1ʳᵉ exécution du 4B + RAG et approchent le 14B et Sonnet + RAG.
  Mais la 2ᵉ exécution du 4B fait 6/8 + 1 partielle : sur 8 questions, l'écart (une réponse) est dans le bruit (§4.11).

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
| Qwen3-4B RAFT v3 / v4 + RAG | 0,38 / 0,37 | 0,51 | 0,26 | 204 | 3,9 | 0 |
| Qwen3-4B + RAG + normalisation | 0,40 (+0,09 si reformulée) | 0,72 | 0,26 | 204 | 3,9 | 0 |
| Qwen3-1.7B + RAG | 0,24 | 0,39 | 0,16 | 362 | 2,2 | 0 |
| Qwen3-1.7B RAFT v2 + RAG | 0,21 | 0,28 | 0,15 | 383 | 2,2 | 0 |

\* Pour `claude -p`, les débits et latences sont indicatifs : ils incluent le réseau et les tokens de réflexion. Le prompt RAG fait ~2 100 tokens pour les Qwen (k=4) et ~4 800 pour Sonnet (k=5).

**Longueur des réponses** : 25 mots en moyenne pour le 4B + RAG (29 tokens médians), 14,5 mots pour le RAFT v2 (21 tokens), 14,9 pour la v3 et 15,2 pour la v4,
alors que leurs réponses d'entraînement font 20,7 (v3) et 29 mots (v4 pour les nouveaux exemples). C'est l'une des causes de l'écart de score (§4.7).

**Normalisation** : mesurée GPU libre sur les 40 saisies du jeu joueurs, la reformulation par le 4B prend **0,09 s** (médiane, max 0,12 s) quand elle a lieu
(18 saisies sur 40) ; la correction des noms seule est instantanée.

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
3. **Un SLM de 4B avec RAG se place à 6-7 points de Sonnet + RAG et à 3-4 points du 14B + RAG** sur le test (86,6 à 87,9 % selon l'exécution),
   et **au niveau de Sonnet + RAG sur de vraies questions de joueurs** (§4.9), pour un coût marginal nul. Il est ~7 fois plus rapide que Sonnet + RAG et ~2,7 fois plus rapide que le 14B, avec 2,7 fois moins de VRAM. Il tient sur un portable (démo Mac).
4. **Les frontier sans RAG ne connaissent pas l'actualité du domaine.** Ils obtiennent 5 à 16 % sur les questions temporelles et 0/8 sur la Saison 5. En revanche, ils s'abstiennent au lieu d'halluciner (0 % d'hallucination, 32 à 44 % d'abstention).
5. **Le RAFT ne bat pas le modèle de base + RAG en score global, mais il change le comportement** :
   - 4B : 83,8 % (v2) contre 86,6 %, soit un écart à la limite de la significativité (§8) ;
   - 1.7B : 80,6 % contre 80,9 %, égalité ;
   - **hallucinations du 1.7B divisées par trois** (1 sur 16 au lieu de 3) : c'est le cas visé par RAFT, un très petit modèle qui lit mal des passages bruités ;
   - **meilleur sur la Saison 5** (6/8 + 1 partielle pour les deux RAFT v2), là où l'information est vraiment nouvelle ;
   - réponses plus courtes, latence p95 plus basse (0,51 s contre 0,78 s).
6. **Les RAFT v3 et v4 ne changent pas ce constat** (84,7 et 85,3 % sur le test, sous le 4B de base ; §4.7) et **perdent nettement sur le jeu joueurs**
   (55 à 64 % contre 74 % pour le 4B de base + normalisation ; §4.9). Le levier, c'est la recherche et la préparation de la question, pas le fine-tuning (§4.12).

### 4.7 Diagnostic du RAFT, RAFT v2 à v4

**RAFT v1 (13 oct.)** : 83,6 %, avec 20 abstentions contre 8 pour le 4B de base. Diagnostic sur `raft_val` (même distribution que l'entraînement) :
- sur les exemples avec oracle, le RAFT ne refuse que dans 3 % des cas (base : 2 %) ; la sur-abstention n'apparaît que sur le test ;
- cause : les questions d'entraînement recopiaient la formulation du passage oracle. Face aux questions du test, formulées autrement, le modèle ne reconnaît plus le passage et refuse ;
- ~12 % des étiquettes « refus » étaient fausses, la réponse étant en fait dans les passages ;
- une partie des réussites du modèle de base vient de sa mémoire paramétrique (G41, G43) et non des passages.

**RAFT v2 (17 oct.)** : reformulations, refus vérifiés, p_oracle 0,9 (§2.6). Le choix a été fait sur le jeu de dev :

| Jeu de dev (327 q.) | Score % | Abstention | Halluc. |
|---|---|---|---|
| Qwen3-4B + RAG | 83,3 | 18 | 0 |
| Qwen3-4B RAFT v1 + RAG | 80,3 | 40 | 0 |
| **Qwen3-4B RAFT v2 + RAG** | **87,2** | 15 | 0 |
| Qwen3-1.7B RAFT v2 + RAG | 83,8 | 13 | 0 |

**Sur le test, le gain ne se transfère qu'en partie** : 83,8 % contre 83,6 % pour la v1, avec des abstentions passées de 20 à 12, mais toujours sous le 4B de base (86,6 %). Comparaison question par question avec le 4B de base : le RAFT v2 gagne 8 questions (S04, T30, G45, E09…) et en perd 19 :
- **réponses incomplètes sur les questions composées** : la majorité des pertes sont des « partielles » (E21, L41, L45, L48, M14…). Les exemples RAFT ne contiennent que des paires à un seul fait, et le modèle a appris à ne donner qu'un fait ;
- **quelques refus restants** alors que la réponse est dans les passages (G41, G43, T14).

Le jeu de dev n'a pas vu ce défaut, faute de questions composées.

**RAFT v3 (27-28 oct.)** : d'abord écartée (ses corrections seraient venues des erreurs du test), elle a finalement été construite à partir
de défauts visibles **hors du test** : réponses à un seul fait sur des questions composées (visibles sur les paires de validation) et saisies
de joueurs mal comprises (jeu joueurs J01-J15). Données : §2.6. Entraînement : 880 pas, 3 h 02.
- Dev 87,3 % (v2 : 87,2), test 84,7 % (v2 : 83,8), joueurs 55,0 % avec normalisation (v2 k6 : 63,8).
- Les réponses restent courtes (14,9 mots contre 14,5) malgré des réponses d'entraînement de 20,7 mots : le signal porte sur ~1,6 % des tokens
  d'un exemple, en une epoch. Gain net sur S03 (Saison 5), question composée, désormais complète.

**RAFT v4 (29 oct.)** : diagnostic de §4.8 (les erreurs restantes des SLM sont des erreurs de lecture) et du jeu joueurs (conditionnels, valeurs
actuelles entre deux patchs, listes) : questions difficiles écrites par `qwen3.6`, réponses du 35B lui-même en lisant les vrais passages (distillation). Données : §2.6. Entraînement : 166 pas, 37 min.
- Dev 85,3 %, test **85,3 %** (meilleur RAFT, et seul gain net : esport 76,7 % contre 68,6 % pour la v2), joueurs 57,5 % avec normalisation.
- Limite : le 35B n'est d'accord avec la référence que pour 57 % des questions difficiles (1 289 sur 2 256) ; distiller un professeur à peine meilleur que
  l'élève sur ces questions ne pouvait pas apporter beaucoup.

| RAFT 4B | Ce qui change | Dev | Test | Joueurs (40) | Abstentions joueurs |
|---|---|---|---|---|---|
| (base) Qwen3-4B + RAG | — | 83,3 | 86,6 | 66,2 | 3 |
| (base) + normalisation | saisie corrigée, reformulée si besoin | 82,4 | 87,9* | **73,8** | 2 |
| v1 | passages, distracteurs, refus | 80,3 | 83,6 | — | — |
| v2 (k=6 pour joueurs) | reformulations, refus vérifiés | 87,2 / 88,5 (k6) | 83,8 / 84,0 (k6) | 63,8 | 7 |
| v3 (+ normalisation pour joueurs) | questions composées, saisies bruitées | 87,3 | 84,7 | 55,0 | 7 |
| v4 (+ normalisation pour joueurs) | questions difficiles, réponses du 35B | 85,3 | 85,3 | 57,5 | 7 |

\* 2ᵉ exécution du 4B + RAG (2 questions du test sur 235 modifiées par la normalisation, §4.11).

### 4.8 D'où viennent les erreurs des bras + RAG : recherche ou lecture ?

Pour chaque question répondable non jugée `correct` (partielle, incorrecte ou abstention), `qwen3.6` vérifie si les passages reçus contenaient la réponse de référence (`bench/errors.py`, même prompt que la vérification des refus RAFT ; `eval/report/error_sources.md`). Si la réponse est absente, c'est une erreur de **recherche** : aucun modèle ne pouvait répondre à partir de son contexte. Si elle est présente, c'est une erreur de **lecture**.

| Configuration | Erreurs | Recherche | Partiel | Lecture |
|---|---|---|---|---|
| Claude Sonnet + RAG (k=5) | 18 | 11 (61 %) | 1 | 6 (33 %) |
| Qwen3-14B + RAG (k=5) | 28 | 12 (43 %) | 2 | 14 (50 %) |
| Qwen3-4B + RAG | 41 | 13 (32 %) | 2 | 25 (61 %) |
| Qwen3-4B RAFT v1 + RAG | 48 | 13 (27 %) | 3 | 31 (65 %) |
| Qwen3-4B + RAG, 2ᵉ exécution (normalisation) | 36 | 13 (36 %) | 2 | 20 (56 %) |
| Qwen3-4B RAFT v2 + RAG | 48 | 13 (27 %) | 2 | 32 (67 %) |
| Qwen3-4B RAFT v3 + RAG | 48 | 13 (27 %) | 2 | 32 (67 %) |
| Qwen3-4B RAFT v4 + RAG | 44 | 13 (30 %) | 2 | 28 (64 %) |
| Qwen3-1.7B + RAG | 49 | 13 (27 %) | 2 | 33 (67 %) |
| Qwen3-1.7B RAFT v2 + RAG | 56 | 13 (23 %) | 2 | 40 (71 %) |

(1 question non vérifiée par bras k=4, sortie JSON invalide. Seule la dernière réponse jugée de chaque question compte, comme dans le rapport du banc : une première version du décompte, corrigée le 31 oct., comptait aussi les anciens verdicts des 9 questions rejugées après la mise à jour du test, d'où 21, 33, 46 et 54 erreurs pour Sonnet, le 14B, le 4B et le 1.7B.)

**Lecture.**
- **La limite propre au RAG est la même pour tous** : 11 à 13 questions (~5-6 % des 219) dont la réponse n'était dans aucun des passages reçus (ex. E32 : la page du joueur Shu n'est pas remontée, seules des pages de tournoi l'ont été). Plus de passages ou un meilleur moteur de recherche (reranker, découpe) sont les seuls leviers.
- **Plus le modèle est petit, plus ses erreurs sont des erreurs de lecture** : 33 % pour Sonnet, 50 % pour le 14B, 56 à 71 % pour les SLM. Pour un modèle fort, c'est la recherche qui limite ; pour un SLM, c'est la lecture, en grande partie des réponses incomplètes aux questions composées (§4.7).
- Le RAFT ne réduit pas le nombre d'erreurs de lecture sur ce test, ce qui est cohérent avec §4.7 : il apprend à s'abstenir et à repérer le bon passage, mais pas à répondre à toutes les parties d'une question.
- **Marge d'un reranker** (29 oct.) : pour les 13 erreurs de recherche du 4B + RAG et de Sonnet + RAG, `qwen3.6` vérifie si la réponse figure dans les
  **20 premiers** passages (par groupes de 5). Trouvée pour **5 sur 13** (rangs 5, 7, 9, 16, 17 : E12, T32, T36, T01, E17), dont 3 dans le top 10 ;
  absente du top 20 pour 8 (E16, E32, E34, E36, E38, G49, L38, S08). Un reranker parfait sur le top 20 gagnerait donc **au plus ~5 questions sur 219
  (+2,3 points)**, ~3 en pratique (top 10), soit de l'ordre du bruit d'exécution, pour +1 à 2 s par question : **non implémenté**. Les 8 autres demandent
  une autre découpe ou une autre requête (questions « quel héros… » sans nom, voir J39 en §4.9).
- **Bruit** : deux exécutions du même 4B + RAG (mêmes passages pour les 14 questions dont le verdict change) donnent 41 puis 36 erreurs, dont 25 puis 20 de lecture.
  Le nombre d'erreurs de recherche (13) est stable ; le bruit sur la lecture est d'environ 5 erreurs (§4.11). Les RAFT (28 à 32 erreurs de lecture) n'en font pas moins que le 4B de base (20 à 25 selon l'exécution) : au mieux autant, plutôt un peu plus.
- Vérification automatique par un LLM local : indicative. Contrôlée à la main sur E32 (recherche), L18 (partiel) et quelques erreurs de lecture (G30 : le passage donne bien 750 PV pour Roadhog, le 4B s'est trompé).

### 4.9 Jeu joueurs (40 questions, 29 oct.)

| Configuration | Score % | J01-J15 | J16-J40 (jamais vues) | Correct | Partiel | Incorrect | Abstention | Halluc. |
|---|---|---|---|---|---|---|---|---|
| Qwen3-14B + RAG (k=5) | **78,8** | 80,0 | 78,0 | 31 | 1 | 5 | 3 | 0 |
| Claude Sonnet + RAG (k=5) | 75,0 | 70,0 | 78,0 | 29 | 2 | 4 | 5 | 0 |
| **Qwen3-4B + RAG + normalisation** | **73,8** | 60,0 | **82,0** | 29 | 1 | 8 | 2 | 0 |
| Qwen3-4B + RAG | 66,2 | 40,0 | **82,0** | 26 | 1 | 9 | 3 | 1 |
| RAFT 4B v2 + RAG (k=6) | 63,8 | 53,3 | 70,0 | 25 | 1 | 7 | 7 | 0 |
| RAFT 4B v4 + RAG + normalisation | 57,5 | 56,7 | 58,0 | 20 | 6 | 7 | 7 | 0 |
| RAFT 4B v3 + RAG + normalisation | 55,0 | 53,3 | 56,0 | 21 | 2 | 10 | 7 | 0 |

Par type de question (points obtenus / questions), 4B + normalisation : fiche 13/16, valeur 5/6, jargon 4,5/7, combinée 3/4, liste 2/5, avis 2/2.
Sonnet + RAG : jargon 5/7, liste 2,5/5. Toutes les configurations plafonnent sur les **listes** (2 à 2,5/5).

**Lecture.**
- **Le 4B de base + RAG est au niveau de Sonnet + RAG** sur de vraies saisies de joueurs (73,8 contre 75,0 %), et même devant sur les 25 questions jamais
  utilisées pour régler quoi que ce soit (82 contre 78 %). Avec 25 questions (4 points par question), on dira « au niveau de », pas « meilleur que ».
- **Les RAFT perdent 4 à 7 questions** sur le 4B de base : ils s'abstiennent beaucoup plus (7 contre 2) et ratent du jargon (rez, Bap) et des fiches simples
  (ancien nom de Cassidy, phrase de l'ultime de Sigma). L'entraînement les a rendus prudents et moins souples hors de la distribution des données RAFT.
- **Échecs communs** : J39 (Sombra devenue support en Saison 5 : les notes du 6 oct. ne sont pas retrouvées, « DPS » et « support » contre « Support role » et
  « rework » ; erreur de recherche, tous s'abstiennent. Dès que la question nomme Sombra (« Is Sombra a support now? », « What role is Sombra now? »,
  « sombra role »), la note du patch est retrouvée et le 4B répond Support, avec la source ; « What role is Sombra in Season 5? » retrouve la note mais le 4B
  répond qu'elle ne parle pas de la Saison 5 : la note est datée « October 6, 2026 », pas « Season 5 »), J18 (« champion des Junkers » : tous répondent Junker Queen ; question ambiguë, référence à valider),
  J08 (héros de la Saison 4, liste), J28-J29 (absents du corpus : abstention, sauf le 14B qui invente sur J28).

### 4.10 Normalisation de la question (`rag/rewrite.py`, sans entraînement)

1. **Correction des noms d'entités** (rapidfuzz contre les titres des pages d'entités, seuil 85, 80 pour un mot en minuscules ou en tête de saisie ;
   jamais un mot du corpus fréquent, un mot d'un nom propre composé ni une forme dérivée) : « Gesnji » → Genji, « Roadhgo » → Roadhog, « Brigitta » → Brigitte.
2. **Reformulation** en une question complète par le modèle qui répond (Ollama, température 0, exemples en un seul message), **seulement si la saisie n'est
   pas déjà une question complète** (mode `auto` : pas de « ? », pas de mot interrogatif ou moins de 4 mots). Une reformulation qui perd plus de 20 % des mots
   de contenu est rejetée (le RAFT répondait parfois au lieu de reformuler).
3. La question normalisée sert à la recherche **et** au prompt ; cache disque pour la reproductibilité.

| Jeu | Questions reformulées (mode auto) | 4B + RAG | 4B + RAG + normalisation |
|---|---|---|---|
| Joueurs J01-J15 (ont servi à la régler) | 15 / 15 | 40,0 | **60,0** |
| Joueurs J16-J40 (jamais vues) | 3 / 25 (2 corrections de noms) | 82,0 | 82,0 |
| Dev | 0 / 327 | 83,3 | 82,4 (bruit, prompts identiques) |
| Test | 2 / 235 (corrections de noms) | 86,6 | 87,9 (bruit, §4.11) |

La normalisation **aide les saisies en mots-clés et ne nuit pas ailleurs**. La reformulation systématique (mode `always`, testé d'abord) faisait perdre
~3 points sur le dev : paraphrases qui changent la recherche. Coût : 0,09 s quand la reformulation a lieu. Son gain mesuré (+20 points) porte sur les
15 saisies qui ont servi à la mettre au point : il est probablement surestimé.

### 4.11 Bruit d'exécution

Le même modèle, à température 0 et au même prompt, ne donne pas toujours la même réponse avec Ollama (ordre des calculs sur GPU, version du serveur) :
- **dev** : deux exécutions à prompts identiques, 223 réponses sur 327 identiques, ~1 point d'écart de score ;
- **test** : 4B + RAG le 12 oct. puis le 29 oct. (233 questions sur 235 identiques) : **86,6 puis 87,9 %**, 171 réponses sur 235 identiques,
  14 verdicts différents, tous avec les mêmes passages ; erreurs de lecture 29 puis 20.

Conséquence : des écarts de 1 à 3 points entre configurations, sur le test comme sur le dev, ne sont pas interprétables isolément. Les conclusions
s'appuient sur des écarts qui se répètent sur les trois jeux (RAFT sous la base sur le test et le jeu joueurs) ou qui dépassent nettement ce bruit
(RAG contre sans RAG, jeu joueurs J01-J15).

### 4.12 Quelle configuration dans quel cas

| Cas | Meilleur SLM | Écart | Commentaire |
|---|---|---|---|
| Questions de joueurs (fautes, mots-clés, jargon) | **4B de base + RAG + normalisation** (73,8 %) | +10 à +19 points sur les RAFT | au niveau de Sonnet + RAG (75 %) |
| Jeu de test (questions rédigées) | **4B de base + RAG** (86,6-87,9 %) | +1 à +3 points sur le meilleur RAFT (v4, 85,3) | lore, cartes, patchs |
| Esport | RAFT v4 (76,7 %) | +2 à +5 points | seul gain du v4 hors dev |
| Questions du dev (même distribution que l'entraînement) | RAFT v2 k6 (88,5 %) | +5 points | gain qui ne se transfère pas |
| Latence | RAFT (0,37 s) | ~20 % plus rapide | réponses plus courtes |
| Hallucination, très petit modèle | **RAFT 1.7B** (1/16) | contre 3/16 | le cas visé par RAFT |
| Hallucination, 4B | égalité (0/16) | | le 4B + RAG n'invente déjà rien |
| Sans RAG | aucun | SFT 11,5 %, 16/16 hallucinations | le fine-tuning seul n'apprend pas les faits |

**Pourquoi le RAFT ne bat pas le modèle de base** :
1. **Qwen3-4B sait déjà lire des passages** : modèle *instruct* récent, 86,6 % avec RAG sans entraînement. L'article RAFT (2024) mesurait ses gains sur
   des modèles qui lisaient mal (Llama 2 7B). La marge restante dépend de la recherche (13-14 questions) ou de la taille du modèle (listes, croisements).
2. **Le RAFT apprend une forme** : questions générées par un LLM dans un style homogène, réponses courtes. D'où le gain sur le dev, généré de la même
   façon, et la perte sur des questions humaines.
3. **Il devient prudent** : les exemples de refus (8 à 19 % selon la version) le poussent à s'abstenir hors de l'ordinaire (7 abstentions sur 40 au jeu
   joueurs contre 2). Utile au 1.7B qui hallucinait, pénalisant pour le 4B qui n'hallucinait pas.
4. **Signal d'entraînement faible** : la loss porte sur ~1,2 à 1,6 % des tokens, en une epoch ; un entraînement plus fort risquerait l'oubli.

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
| Données RAFT v3 : questions composées (`compose`) | 4 h 35 pour 3 898 questions (~4,2 s/ex, GPU en partie partagé) | GPU (`qwen3.6`) |
| Données RAFT v4 : questions difficiles (`hard`) puis réponses du 35B (`teach`) | 1 h 30 (3 000 graines, ~2 s/ex) + 2 h 26 (2 256 questions, ~4 s/ex) | GPU (`qwen3.6`) |
| Banc jeu joueurs (40 q.) | < 1 min par config locale, quelques minutes pour Sonnet + RAG | GPU / abonnement |
| Export GGUF Q4_K_M | 1 min (1.7B, 1,1 Go) à 3 min (4B, 2,5 Go) ; 7 min la première fois (compilation de llama.cpp) | CPU / GPU |
| Banc local (235 q.) | 1 à 5 min par configuration | GPU |
| Banc frontier (235 q.) | ~24 min par config sans RAG, ~14 min avec RAG | abonnement |
| Jugement (235 q.) | ~1,5 min par config (lots de 15, ~5 s/lot) | abonnement |

**Entraînements QLoRA** (RTX 5070 Ti sous WSL2, `eval/report/training.md`) :

| Run | Exemples | Pas | Durée | s/ex | tok/s | Pic VRAM (Go) | Loss train / val |
|---|---|---|---|---|---|---|---|
| RAFT 4B v1 | 14 250 | 891 | 3 h 22 | 0,85 | 2 322 | 13,9 | 0,246 / 0,240 |
| RAFT 4B v2 | 14 072 | 880 | 3 h 29 | 0,89 | 2 218 | 13,8 | 0,278 / 0,275 |
| RAFT 4B v3 | 14 072 | 880 | 3 h 02 | 0,76 | 2 614 | 13,8 | 0,326 / 0,328 |
| RAFT 4B v4 | 2 650 | 166 | 37 min | 0,77 | 2 625 | 13,4 | 0,395 / 0,354 |
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

### 5.2 Coût d'usage (par requête) : SLM local contre LLM + recherche web

Le vrai concurrent d'un SLM + RAG n'est pas un LLM nu, mais un **LLM frontier équipé d'un outil de recherche web**, qui se met à jour seul. Nous l'avons ajouté comme bras `claude-sonnet-web` (outil WebSearch de Claude Code, sur les 74 questions temporelles), et mesuré la consommation électrique des bras locaux (`bench/power.py`, `eval/report/power.jsonl`).

**Protocole énergie** : puissance de la carte graphique relevée 10 fois par seconde (`nvidia-smi`) pendant les 235 questions, consommation au repos (21 à 28 W) soustraite ; encodage des questions inclus ; CPU **estimé** à 35 W pendant une inférence GPU (charge légère, valeur moyenne) et à 120 W (TDP du Ryzen 7 9800X3D, majorant) pour l'inférence sur CPU seul. Les autres composants (carte mère, RAM, disque) et la consommation au repos de la machine ne sont pas comptés. Prix : **0,2001 €/kWh** (tarif bleu EDF, option Base 6 kVA, en vigueur depuis le 1er août 2026). Tarifs API officiels Anthropic : Sonnet 5.5 à 2 $ / 10 $ par million de tokens en entrée / sortie, recherche web à 10 $ pour 1 000 recherches. Change : 1 € ≈ 1,12 $ (11 oct. 2026).

| Configuration | Score temporel (74 q.) | Saison 5 | Latence | Énergie / question | Coût / question | 10 000 questions / jour pendant 1 an |
|---|---|---|---|---|---|---|
| Claude Sonnet seul | 5,4 % | 0/8 | 5,6 s | — | 0,007 $ | — |
| **Claude Sonnet + recherche web** | **73,6 %** | 4/8 + 1 p. | **16,7 s** (p95 30,7 s) | — | **0,033 $ ≈ 0,030 €** | **~108 500 €** |
| Claude Sonnet + notre RAG (API) | 92,6 % | 7/8 | 3,1 s | — | 0,011 $ ≈ 0,010 € | ~35 900 € |
| Qwen3 14B + RAG (GPU) | 87,2 % | 7/8 | 1,3 s | 0,092 Wh | 1,8 × 10⁻⁵ € | 67 € |
| **Qwen3 4B + RAG (GPU)**, modèle de la démo | 79,7-83,1 %** | 5-6/8 + 1 p. | 0,51 s | 0,029 Wh | 5,9 × 10⁻⁶ € | **21 €** |
| Qwen3 4B RAFT v2 + RAG (GPU) | 81,8 % | 6/8 + 1 p. | 0,41 s | 0,024 Wh | 4,8 × 10⁻⁶ € | 17 € |
| **Qwen3 1.7B RAFT v2 + RAG (GPU)** | 77,7 % | 6/8 + 1 p. | **0,26 s** | **0,012 Wh** | **2,3 × 10⁻⁶ €** | **8 €** |
| Qwen3 1.7B RAFT v2 + RAG (CPU seul) | (idem) | (idem) | 4,1 s | 0,135 Wh | 2,7 × 10⁻⁵ € | 99 € |
| Qwen3 4B + RAG (CPU seul) | (idem) | (idem) | 10,4 s | 0,348 Wh | 7,0 × 10⁻⁵ € | 254 €* |

\** Deux exécutions (12 et 29 oct.). La normalisation ajoute ~0,09 s et un appel au même modèle quand la saisie est reformulée (énergie non mesurée à part,
de l'ordre d'une génération courte).

\* 10,4 s par question : une seule machine plafonne à ~8 300 questions par jour en traitement séquentiel. Sur CPU seul, les réponses sont identiques à celles du GPU (mêmes poids), seule la vitesse change ; la mesure CPU porte sur 60 (1.7B) et 30 (4B) questions. Coût Sonnet + recherche web : ~6 000 tokens en entrée (pages de résultats incluses), ~900 en sortie, ~1,2 recherche par question ; ce calcul retrouve le coût équivalent rapporté par `claude -p` (0,034 $). Le bras web n'a pas été passé sur les questions sans réponse.

**Lecture.**
- **Sonnet + recherche web se met bien à jour** (5,4 % → 73,6 % sur les questions temporelles), mais il fait **moins bien que nos SLM + RAG** (77,7 à 81,8 %) : il tombe sur des articles de presse ou des pages obsolètes plutôt que sur les notes officielles (S04 : refus faute de source fiable). Un index construit sur des sources choisies vaut mieux qu'une recherche web générique.
- **Coût marginal** : par question, le SLM local coûte de **1 000 fois** (1.7B sur CPU) à **13 000 fois** (1.7B sur GPU) moins cher que Sonnet + recherche web, et de 360 à 4 300 fois moins que Sonnet + RAG via l'API.
  Pour le 4B de base + RAG, modèle de la démo : **~5 000 fois** moins cher que Sonnet + recherche web sur GPU (430 fois sur CPU seul, mais 10 s par réponse),
  avec un meilleur score sur les questions temporelles (80-83 % contre 74 %).
- **Latence** : 0,3 à 0,5 s contre 17 s.

**Amortissement du matériel** (prix d'achat ÷ économie par question, face à Sonnet + recherche web / Sonnet + RAG API) :

| Matériel | Questions pour amortir | À 1 000 questions / jour |
|---|---|---|
| RTX 5070 Ti (~1 200 €, notre machine) | 40 400 / 122 200 | 40 / 122 jours |
| Machine sans carte graphique à 300 € (1.7B sur CPU) | 10 100 / 30 600 | 10 / 31 jours |
| Machine à 150 € ou machine déjà possédée | 5 000 / 15 300, ou immédiat | 5 / 15 jours |

Le prix d'une machine minimale est une hypothèse (les prix de la RAM ont fortement monté en 2026 : le Raspberry Pi 5 16 Go est passé à 205 $). Le 1.7B quantifié tient en 1,1 Go de fichier et ~2,2 Go de mémoire ; un PC à 4-8 Go de RAM suffit, mais un processeur d'entrée de gamme sera plus lent que notre Ryzen 7 9800X3D (latence de 4 s mesurée ici, à multiplier).

**Limites de cette comparaison** : CPU estimé et non mesuré ; consommation au repos de la machine non comptée (pour un service allumé 24 h/24, elle dépasse la consommation marginale : la carte seule consomme ~26 W au repos, soit ~46 €/an) ; l'énergie et l'infrastructure côté fournisseur sont incluses dans le prix de l'API, pas mesurées. Le coût de construction (génération 25,7 h, entraînement) est un coût unique, non amorti ici.

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
| **SLM + RAFT + RAG** | tout ce qui précède + construction des exemples RAFT | le plus élevé | génération + 7 min + 1 h 15 à 3 h 30 (+ ~2 h pour la v2, ~4 h 30 pour la v3, ~4 h pour la v4) | secondes (index), réentraînement optionnel | réponses trop courtes, prudence excessive, pas de gain mesuré en 4B |
| SLM + RAG + normalisation | RAG + correction des noms (rapidfuzz) + un appel au modèle | faible (`rag/rewrite.py` ~220 lignes) | nul | secondes | reformulation qui change la recherche (d'où le mode `auto`) |
| LLM local 14B + RAG | RAG + GPU 12 Go ou plus | moyen | idem RAG | secondes | latence ×2,7, VRAM ×2,7 |
| Frontier (+ RAG) | abonnement / API (+ RAG) | faible | nul | dépend du fournisseur | coût récurrent, données envoyées à un tiers, connaissances datées sans RAG |

### 6.2 Taille du code (Python)

| Package | Rôle | Fichiers | Lignes |
|---|---|---|---|
| `scraper/` | collecte, nettoyage, découpe, refresh, Blizzard | 12 | 1 021 |
| `gen/` | génération Q/R, templates, dataset | 4 | 1 169 |
| `rag/` | BM25, embeddings, retriever hybride, RAFT, RAFT v2 à v4 et jeu de dev (`augment.py`), normalisation (`rewrite.py`) | 11 | 1 850 |
| `bench/` | banc, backends, juge, rapport, jeux de dev et joueurs, provenance des erreurs, énergie | 10 | 1 198 |
| `train/` | QLoRA SFT/CPT/RAFT, export GGUF | 6 | 375 |
| `demo/` | démo de soutenance, paquet pour le Mac | 3 | 278 |
| **Total** | | 46 | **~5 890** |

### 6.3 Contraintes d'environnement rencontrées

- **Smart App Control** (Windows) bloque les `.exe` des venv, `uv run` et `uv sync`. Contournement : interpréteur de base uv avec `PYTHONPATH` vers les paquets du venv.
- **Fine-tuning sous WSL2** (Ubuntu 24.04) : Unsloth et bitsandbytes s'utilisent mal sous Windows, et le GPU Blackwell exige CUDA ≥ 12.8.
- **Mémoire** : le modèle de génération occupe ~16 Go de RAM, WSL jusqu'à 15 Go pendant un entraînement, et les tâches de fond longues sont tuées si la RAM manque. Tous les traitements longs sont donc lancés en processus indépendants et sont **reprenables** (append JSONL, fichiers STOP, `--resume`). Les entraînements de la nuit du 17 oct. ont tourné en une chaîne unique (script `.bat`, fichier d'état), sans surveillance.
- **Assistance et surveillance** : le code a été écrit avec Claude Code (Claude Opus 5.5), qui a aussi lancé les chaînes longues (génération Q/R, données RAFT,
  entraînements, exports, bancs, jugements), les a enregistrées dans un panneau de suivi et les a surveillées, souvent de nuit : relance après un arrêt,
  diagnostic des échecs (chaîne qui attendait le mauvais processus, modèles qui se disputaient le GPU), mise en veille du PC à la fin.
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
| 26 oct. | Mise à jour du dossier, échantillon de vérification manuelle du juge, préparation de la soutenance ; script de démo | `a12dfd7`, `e927ba4` |
| 27-28 oct. | Jeu joueurs (J01-J15) ; normalisation des questions ; balayage du RAG (k, passages par page) ; données et entraînement RAFT v3 | `80220d5`, `7722c62` |
| 29 oct. (nuit) | RAFT v4 (questions difficiles, réponses du 35B), entraînement, bancs dev/joueurs/test des finalistes, en chaîne unique | `0f0d816` |
| 29 oct. | Jeu joueurs élargi à 40 questions (J16-J40), 14B et Sonnet + RAG ; démo sur le 4B de base + normalisation | `9515f21`, `734ce66` |

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
| RAFT v3 et v4 réglés sans regarder le test | d'abord écartée pour ne pas régler le système sur le test, la v3 a été construite à partir de défauts vus sur le dev et le jeu joueurs ; même règle pour la v4 |
| Jeu joueurs | le dev généré favorisait le RAFT ; il fallait de vraies saisies pour juger l'usage réel |
| Normalisation en mode `auto` | la reformulation systématique faisait perdre ~3 points sur le dev |
| Démo sur le 4B de base + RAG + normalisation | meilleur SLM sur le test et le jeu joueurs, et pas de modèle fine-tuné à installer |

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
11. **Jeu de dev trop proche des données RAFT** : généré à partir des mêmes paires, il a favorisé les RAFT v2 à v4 (+2 à +5 points) sans que le gain se transfère. Leçon : tester sur de vraies questions.
12. **Bruit d'exécution d'Ollama** : à température 0, une réponse sur quatre change d'une exécution à l'autre ; un 4B identique passe de 86,6 à 87,9 % (§4.11).
13. **Modèles qui se partagent le GPU** : le 35B (~13,5 Go de VRAM) et un 4B ne tiennent pas ensemble ; Ollama les échange à chaque requête (~30 s). Une chaîne de nuit
    qui attendait le mauvais processus (le `cmd` parent au lieu de `python`) a lancé des bancs pendant une génération ; corrigé en attendant le PID de `python`.
14. **Reformulation par le RAFT** : le modèle fine-tuné répondait parfois au lieu de reformuler, ou répétait le mot interrogatif ; garde sur les mots de contenu.

---

## 8. Limites et points à vérifier

- **Juge LLM vérifié à la main** : 112 verdicts tirés (8 par configuration, stratifiés par verdict : les abstentions et hallucinations y sont surreprésentées), 111 relus (`eval/review/sample.csv`, précisions du relecteur dans `human_note`). **Accord 100 %, kappa de Cohen 1,00.** Limites : un seul relecteur, qui voyait le verdict et la justification du juge en relisant (biais de confirmation possible) ; échantillon stratifié, donc l'accord porte surtout sur les cas difficiles et ne se transpose pas directement à l'ensemble des réponses.
- **Biais de construction** : le test et l'index proviennent du même corpus, ce qui avantage les bras RAG face aux frontier sans RAG. Les questions temporelles et la Saison 5 montrent toutefois un vrai besoin d'information fraîche.
- **Le test a été consulté pour le diagnostic du RAFT** (v1 puis v2) : les écarts observés dessus servent d'explication, pas de réglage. Les v3 et v4 ont été
  construites à partir du dev et du jeu joueurs uniquement.
- **Jeu joueurs** : 40 questions seulement (une question = 2,5 points) ; J01-J15 ont servi à régler la normalisation (son gain y est probablement surestimé) ;
  références de J08, J10, J18 et J22 encore à valider.
- **k différent** entre les bras : 4 pour les SLM, 5 pour le 14B et Sonnet.
- **Couverture « couvert / non couvert »** : heuristique, indicative.
- **Une seule graine et bruit d'exécution**, pas d'intervalles de confiance : deux exécutions du même 4B donnent 86,6 et 87,9 % (§4.11) ; avec n = 219, ±2 à 3 points
  ne sont pas significatifs. Les écarts RAFT / base sur le test (1,3 à 3 points en 4B, 0,3 en 1.7B) sont dans cette marge ; c'est leur répétition sur le jeu
  joueurs qui rend la conclusion solide. L'écart d'hallucination du 1.7B (1 contre 3 sur 16) porte sur de très petits effectifs.
- **Mesures frontier** (latence, tok/s) indicatives : réseau et tokens de réflexion inclus.

## 9. Reste à faire et perspectives

Reste à faire :
- [x] Vérification manuelle du juge : accord 100 %, kappa 1,00 (111 verdicts)
- [x] Mesure de la consommation électrique (`bench/power.py`, §5.2)
- [x] Jeu joueurs (40 questions), normalisation, RAFT v3 et v4
- [ ] Démo sur le Mac (4B de base + RAG + normalisation, `docs/REPRISE_MAC.md`) et vidéo de secours
- [ ] Validation des références J08, J10, J18, J22 du jeu joueurs
- [ ] Présentation de soutenance ; citer Fandom et Liquipedia (CC-BY-SA, attribution) et Blizzard (notes de patch)

Perspectives (non réalisées) :
- **Recherche** : la limite commune à tous les modèles (§4.8). Un reranker du top 20 récupérerait au plus 5 des 13 erreurs de recherche (mesuré, §4.8) ;
  le reste demande une autre découpe (par capacité) ou de transformer les questions « quel héros… » sans nom (J39) en recherche par attribut, via une table structurée.
- **Questions de liste** (héros d'une saison, d'un rôle) : table structurée des héros interrogée directement plutôt que des passages ; tous les modèles y échouent.
- **Jeu joueurs plus grand** (100-200 questions) et jeu de dev construit sur de vraies questions, pour régler sans biais vers le RAFT.
- Plusieurs graines et intervalles de confiance (bootstrap) pour les écarts de quelques points.
- Parser les brackets Liquipedia pour poser des questions « qui a gagné X ».
- Améliorer le retriever sur les passages longs (S08) : découpe plus fine ou reranker.

## 10. Attributions

- Overwatch Fandom wiki — contenu sous licence CC-BY-SA.
- Liquipedia Overwatch — contenu sous licence CC-BY-SA 3.0 (attribution obligatoire).
- Notes de patch officielles Overwatch — © Blizzard Entertainment, utilisées à des fins de recherche, source citée.
- Modèles : Qwen3 (Apache 2.0), GGUF Unsloth ; génération `qwen3.6:35b-a3b` (Apache 2.0).
- Outils : Claude Sonnet (Anthropic), juge des réponses ; Claude Code (Claude Opus 5.5, Anthropic), développement assisté, lancement et surveillance
  des traitements longs (génération, entraînement, bancs).
