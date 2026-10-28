# Rapport du banc d'evaluation OW-SLM

Score : correct = 1, partial = 0.5, le reste = 0. Jeu de test fige : `eval/test_set.jsonl`.
Sources du corpus : Overwatch Fandom wiki (CC-BY-SA) et Liquipedia Overwatch (CC-BY-SA 3.0, attribution obligatoire).

## Exactitude globale

| config | n | score global % | score repondables % | correct | partial | incorrect | abstained | hallucinated |
|---|---|---|---|---|---|---|---|---|
| qwen3-4b-rag | 15 | 76.7 | 75.0 | 11 | 1 | 3 | 0 | 0 |
| slm-4b-raft-v2-rag | 15 | 56.7 | 53.6 | 8 | 1 | 5 | 1 | 0 |
| slm-4b-raft-v2-rag-ent | 15 | 60.0 | 57.1 | 8 | 2 | 3 | 2 | 0 |
| slm-4b-raft-v2-rag-ent5 | 15 | 60.0 | 57.1 | 8 | 2 | 3 | 2 | 0 |

## Par categorie (score %)

| config | lore | gameplay | esport | patch | maps_modes | unanswerable |
|---|---|---|---|---|---|---|
| qwen3-4b-rag | 100.0 (n=4) | 61.1 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v2-rag | 100.0 (n=4) | 27.8 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v2-rag-ent | 100.0 (n=4) | 33.3 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v2-rag-ent5 | 100.0 (n=4) | 33.3 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |

## Temporel / couvert (questions repondables, score %)

| config | temporel | non temporel | couvert | non couvert |
|---|---|---|---|---|
| qwen3-4b-rag | n/a (n=0) | 75.0 (n=14) | n/a | n/a |
| slm-4b-raft-v2-rag | n/a (n=0) | 53.6 (n=14) | n/a | n/a |
| slm-4b-raft-v2-rag-ent | n/a (n=0) | 57.1 (n=14) | n/a | n/a |
| slm-4b-raft-v2-rag-ent5 | n/a (n=0) | 57.1 (n=14) | n/a | n/a |

Couvert = fait du test retrouve dans le dataset d'entrainement (`data/dataset/test_coverage.jsonl`, heuristique indicative). Fichier absent : colonnes n/a.

## Hallucination et abstention

| config | n unanswerable | taux d'hallucination % | n repondables | taux d'abstention % |
|---|---|---|---|---|
| qwen3-4b-rag | 1 | 0.0 | 14 | 0.0 |
| slm-4b-raft-v2-rag | 1 | 0.0 | 14 | 7.1 |
| slm-4b-raft-v2-rag-ent | 1 | 0.0 | 14 | 14.3 |
| slm-4b-raft-v2-rag-ent5 | 1 | 0.0 | 14 | 14.3 |

## Performance

| config | latence p50 s | latence p95 s | ttft p50 s | tok/s median | VRAM Mo | cout/requete USD |
|---|---|---|---|---|---|---|
| qwen3-4b-rag | 0.52 | 0.90 | 0.23 | 198.4 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag | 0.34 | 0.44 | 0.26 | 202.5 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-ent | 0.32 | 0.39 | 0.26 | 203.3 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-ent5 | 0.25 | 0.39 | 0.19 | 202.8 | 3878 | 0.0000 |

Local : cout = 0. Claude : cout = equivalent API (abonnement, pas une depense reelle). Pour `claude_cli`, tok/s et latence sont indicatifs (reseau inclus, tokens de reflexion inclus). VRAM lue via Ollama (`/api/ps`), pas `nvidia-smi`.

## Accord juge / verification manuelle

Pas encore de verification manuelle (`ow-bench review-export`, puis remplir `human_verdict`).

## Cout de mise a jour (Saison 5)

A renseigner manuellement (pages re-scrapees, minutes de generation et d'entrainement).
