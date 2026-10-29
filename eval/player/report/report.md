# Rapport du banc d'evaluation OW-SLM

Score : correct = 1, partial = 0.5, le reste = 0. Jeu de test fige : `eval/test_set.jsonl`.
Sources du corpus : Overwatch Fandom wiki (CC-BY-SA) et Liquipedia Overwatch (CC-BY-SA 3.0, attribution obligatoire).

## Exactitude globale

| config | n | score global % | score repondables % | correct | partial | incorrect | abstained | hallucinated |
|---|---|---|---|---|---|---|---|---|
| claude-sonnet-rag | 40 | 75.0 | 74.4 | 29 | 2 | 4 | 5 | 0 |
| qwen3-14b-rag | 40 | 78.8 | 78.2 | 31 | 1 | 5 | 3 | 0 |
| qwen3-4b-rag-auto | 40 | 73.8 | 73.1 | 29 | 1 | 8 | 2 | 0 |
| qwen3-4b-rag-rw-k6 | 15 | 46.7 | 50.0 | 7 | 0 | 4 | 3 | 1 |
| qwen3-4b-rag-rw | 15 | 60.0 | 57.1 | 9 | 0 | 4 | 2 | 0 |
| qwen3-4b-rag | 40 | 66.2 | 67.9 | 26 | 1 | 9 | 3 | 1 |
| slm-4b-raft-v2-rag-auto-k6 | 15 | 46.7 | 42.9 | 7 | 0 | 4 | 4 | 0 |
| slm-4b-raft-v2-rag-ent | 15 | 43.3 | 39.3 | 6 | 1 | 4 | 4 | 0 |
| slm-4b-raft-v2-rag-k6 | 40 | 63.8 | 62.8 | 25 | 1 | 7 | 7 | 0 |
| slm-4b-raft-v2-rag-recent | 15 | 36.7 | 32.1 | 5 | 1 | 5 | 4 | 0 |
| slm-4b-raft-v2-rag-rw-k6 | 15 | 50.0 | 46.4 | 7 | 1 | 4 | 3 | 0 |
| slm-4b-raft-v2-rag-rw | 15 | 43.3 | 39.3 | 6 | 1 | 4 | 4 | 0 |
| slm-4b-raft-v2-rag | 15 | 40.0 | 35.7 | 6 | 0 | 4 | 5 | 0 |
| slm-4b-raft-v3-rag-auto | 40 | 55.0 | 53.8 | 21 | 2 | 10 | 7 | 0 |
| slm-4b-raft-v3-rag-rw | 15 | 43.3 | 39.3 | 6 | 1 | 3 | 5 | 0 |
| slm-4b-raft-v3-rag | 15 | 46.7 | 42.9 | 7 | 0 | 6 | 2 | 0 |
| slm-4b-raft-v4-rag-auto | 40 | 57.5 | 56.4 | 20 | 6 | 7 | 7 | 0 |
| slm-4b-raft-v4-rag | 15 | 46.7 | 50.0 | 6 | 2 | 3 | 3 | 1 |

## Par categorie (score %)

| config | lore | gameplay | esport | patch | maps_modes | unanswerable |
|---|---|---|---|---|---|---|
| claude-sonnet-rag | 92.3 (n=13) | 63.6 (n=22) | 100.0 (n=1) | 50.0 (n=2) | 100.0 (n=1) | 100.0 (n=1) |
| qwen3-14b-rag | 92.3 (n=13) | 70.5 (n=22) | 100.0 (n=1) | 50.0 (n=2) | 100.0 (n=1) | 100.0 (n=1) |
| qwen3-4b-rag-auto | 84.6 (n=13) | 65.9 (n=22) | 100.0 (n=1) | 50.0 (n=2) | 100.0 (n=1) | 100.0 (n=1) |
| qwen3-4b-rag-rw-k6 | 75.0 (n=4) | 33.3 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 0.0 (n=1) |
| qwen3-4b-rag-rw | 75.0 (n=4) | 44.4 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| qwen3-4b-rag | 84.6 (n=13) | 56.8 (n=22) | 100.0 (n=1) | 50.0 (n=2) | 100.0 (n=1) | 0.0 (n=1) |
| slm-4b-raft-v2-rag-auto-k6 | 75.0 (n=4) | 22.2 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v2-rag-ent | 75.0 (n=4) | 16.7 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v2-rag-k6 | 84.6 (n=13) | 50.0 (n=22) | 50.0 (n=1) | 50.0 (n=2) | 100.0 (n=1) | 100.0 (n=1) |
| slm-4b-raft-v2-rag-recent | 75.0 (n=4) | 5.6 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v2-rag-rw-k6 | 75.0 (n=4) | 27.8 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v2-rag-rw | 50.0 (n=4) | 27.8 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v2-rag | 75.0 (n=4) | 11.1 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v3-rag-auto | 65.4 (n=13) | 43.2 (n=22) | 100.0 (n=1) | 50.0 (n=2) | 100.0 (n=1) | 100.0 (n=1) |
| slm-4b-raft-v3-rag-rw | 75.0 (n=4) | 22.2 (n=9) | n/a (n=0) | 50.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v3-rag | 75.0 (n=4) | 22.2 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 100.0 (n=1) |
| slm-4b-raft-v4-rag-auto | 57.7 (n=13) | 54.5 (n=22) | 50.0 (n=1) | 50.0 (n=2) | 100.0 (n=1) | 100.0 (n=1) |
| slm-4b-raft-v4-rag | 75.0 (n=4) | 33.3 (n=9) | n/a (n=0) | 100.0 (n=1) | n/a (n=0) | 0.0 (n=1) |

## Temporel / couvert (questions repondables, score %)

| config | temporel | non temporel | couvert | non couvert |
|---|---|---|---|---|
| claude-sonnet-rag | 75.0 (n=4) | 74.3 (n=35) | n/a | n/a |
| qwen3-14b-rag | 75.0 (n=4) | 78.6 (n=35) | n/a | n/a |
| qwen3-4b-rag-auto | 75.0 (n=4) | 72.9 (n=35) | n/a | n/a |
| qwen3-4b-rag-rw-k6 | n/a (n=0) | 50.0 (n=14) | n/a | n/a |
| qwen3-4b-rag-rw | n/a (n=0) | 57.1 (n=14) | n/a | n/a |
| qwen3-4b-rag | 75.0 (n=4) | 67.1 (n=35) | n/a | n/a |
| slm-4b-raft-v2-rag-auto-k6 | n/a (n=0) | 42.9 (n=14) | n/a | n/a |
| slm-4b-raft-v2-rag-ent | n/a (n=0) | 39.3 (n=14) | n/a | n/a |
| slm-4b-raft-v2-rag-k6 | 75.0 (n=4) | 61.4 (n=35) | n/a | n/a |
| slm-4b-raft-v2-rag-recent | n/a (n=0) | 32.1 (n=14) | n/a | n/a |
| slm-4b-raft-v2-rag-rw-k6 | n/a (n=0) | 46.4 (n=14) | n/a | n/a |
| slm-4b-raft-v2-rag-rw | n/a (n=0) | 39.3 (n=14) | n/a | n/a |
| slm-4b-raft-v2-rag | n/a (n=0) | 35.7 (n=14) | n/a | n/a |
| slm-4b-raft-v3-rag-auto | 75.0 (n=4) | 51.4 (n=35) | n/a | n/a |
| slm-4b-raft-v3-rag-rw | n/a (n=0) | 39.3 (n=14) | n/a | n/a |
| slm-4b-raft-v3-rag | n/a (n=0) | 42.9 (n=14) | n/a | n/a |
| slm-4b-raft-v4-rag-auto | 62.5 (n=4) | 55.7 (n=35) | n/a | n/a |
| slm-4b-raft-v4-rag | n/a (n=0) | 50.0 (n=14) | n/a | n/a |

Couvert = fait du test retrouve dans le dataset d'entrainement (`data/dataset/test_coverage.jsonl`, heuristique indicative). Fichier absent : colonnes n/a.

## Hallucination et abstention

| config | n unanswerable | taux d'hallucination % | n repondables | taux d'abstention % |
|---|---|---|---|---|
| claude-sonnet-rag | 1 | 0.0 | 39 | 12.8 |
| qwen3-14b-rag | 1 | 0.0 | 39 | 7.7 |
| qwen3-4b-rag-auto | 1 | 0.0 | 39 | 5.1 |
| qwen3-4b-rag-rw-k6 | 1 | 100.0 | 14 | 21.4 |
| qwen3-4b-rag-rw | 1 | 0.0 | 14 | 14.3 |
| qwen3-4b-rag | 1 | 100.0 | 39 | 7.7 |
| slm-4b-raft-v2-rag-auto-k6 | 1 | 0.0 | 14 | 28.6 |
| slm-4b-raft-v2-rag-ent | 1 | 0.0 | 14 | 28.6 |
| slm-4b-raft-v2-rag-k6 | 1 | 0.0 | 39 | 17.9 |
| slm-4b-raft-v2-rag-recent | 1 | 0.0 | 14 | 28.6 |
| slm-4b-raft-v2-rag-rw-k6 | 1 | 0.0 | 14 | 21.4 |
| slm-4b-raft-v2-rag-rw | 1 | 0.0 | 14 | 28.6 |
| slm-4b-raft-v2-rag | 1 | 0.0 | 14 | 35.7 |
| slm-4b-raft-v3-rag-auto | 1 | 0.0 | 39 | 17.9 |
| slm-4b-raft-v3-rag-rw | 1 | 0.0 | 14 | 35.7 |
| slm-4b-raft-v3-rag | 1 | 0.0 | 14 | 14.3 |
| slm-4b-raft-v4-rag-auto | 1 | 0.0 | 39 | 17.9 |
| slm-4b-raft-v4-rag | 1 | 100.0 | 14 | 21.4 |

## Performance

| config | latence p50 s | latence p95 s | ttft p50 s | tok/s median | VRAM Mo | cout/requete USD |
|---|---|---|---|---|---|---|
| claude-sonnet-rag | 4.76 | 10.34 | 2.68 | 292.3 | n/a | 0.0222 |
| qwen3-14b-rag | 1.20 | 2.08 | 0.82 | 75.7 | 10489 | 0.0000 |
| qwen3-4b-rag-auto | 0.35 | 0.89 | 0.12 | 193.8 | 3878 | 0.0000 |
| qwen3-4b-rag-rw-k6 | 29.54 | 30.34 | 29.27 | 182.9 | n/a | 0.0000 |
| qwen3-4b-rag-rw | 10.04 | 16.56 | 9.90 | 189.3 | n/a | 0.0000 |
| qwen3-4b-rag | 0.49 | 0.92 | 0.24 | 194.7 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-auto-k6 | 0.49 | 0.63 | 0.39 | 178.2 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-ent | 0.27 | 0.41 | 0.21 | 205.2 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-k6 | 0.55 | 46.91 | 0.47 | 185.5 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-recent | 29.74 | 51.12 | 29.68 | 173.4 | n/a | 0.0000 |
| slm-4b-raft-v2-rag-rw-k6 | 28.44 | 28.85 | 28.37 | 173.3 | n/a | 0.0000 |
| slm-4b-raft-v2-rag-rw | 9.84 | 29.87 | 9.74 | 177.2 | n/a | 0.0000 |
| slm-4b-raft-v2-rag | 0.31 | 0.41 | 0.25 | 203.8 | 3878 | 0.0000 |
| slm-4b-raft-v3-rag-auto | 0.35 | 0.48 | 0.27 | 192.5 | 3878 | 0.0000 |
| slm-4b-raft-v3-rag-rw | 0.27 | 0.36 | 0.20 | 198.9 | 3878 | 0.0000 |
| slm-4b-raft-v3-rag | 0.31 | 0.51 | 0.23 | 200.2 | 3878 | 0.0000 |
| slm-4b-raft-v4-rag-auto | 0.33 | 0.48 | 0.24 | 195.3 | 3878 | 0.0000 |
| slm-4b-raft-v4-rag | 0.31 | 0.45 | 0.24 | 206.8 | 3878 | 0.0000 |

Local : cout = 0. Claude : cout = equivalent API (abonnement, pas une depense reelle). Pour `claude_cli`, tok/s et latence sont indicatifs (reseau inclus, tokens de reflexion inclus). VRAM lue via Ollama (`/api/ps`), pas `nvidia-smi`.

## Accord juge / verification manuelle

Pas encore de verification manuelle (`ow-bench review-export`, puis remplir `human_verdict`).

## Cout de mise a jour (Saison 5)

A renseigner manuellement (pages re-scrapees, minutes de generation et d'entrainement).
