# Rapport du banc d'evaluation OW-SLM

Score : correct = 1, partial = 0.5, le reste = 0. Jeu de test fige : `eval/test_set.jsonl`.
Sources du corpus : Overwatch Fandom wiki (CC-BY-SA) et Liquipedia Overwatch (CC-BY-SA 3.0, attribution obligatoire).

## Exactitude globale

| config | n | score global % | score repondables % | correct | partial | incorrect | abstained | hallucinated |
|---|---|---|---|---|---|---|---|---|
| claude-opus | 235 | 56.0 | 52.7 | 120 | 23 | 21 | 71 | 0 |
| claude-sonnet | 235 | 43.2 | 39.0 | 91 | 21 | 27 | 96 | 0 |
| claude-sonnet-rag | 235 | 93.8 | 93.4 | 217 | 7 | 0 | 11 | 0 |
| claude-sonnet-web | 74 | 73.6 | 73.6 | 51 | 7 | 4 | 12 | 0 |
| qwen3-1.7b-base | 235 | 2.3 | 1.6 | 3 | 5 | 203 | 10 | 14 |
| qwen3-1.7b-rag | 235 | 80.9 | 80.8 | 183 | 14 | 31 | 4 | 3 |
| qwen3-14b | 235 | 12.6 | 10.7 | 21 | 17 | 170 | 17 | 10 |
| qwen3-14b-rag | 235 | 90.6 | 90.0 | 207 | 12 | 7 | 9 | 0 |
| qwen3-4b-base | 235 | 4.7 | 3.2 | 5 | 12 | 195 | 11 | 12 |
| qwen3-4b-rag | 235 | 86.6 | 85.6 | 194 | 19 | 14 | 8 | 0 |
| slm-1.7b-raft-rag | 235 | 80.6 | 79.7 | 178 | 23 | 25 | 8 | 1 |
| slm-4b-cpt-sft | 235 | 14.9 | 16.0 | 21 | 28 | 169 | 1 | 16 |
| slm-4b-raft-rag | 235 | 83.6 | 82.4 | 187 | 19 | 9 | 20 | 0 |
| slm-4b-raft-v2-rag | 235 | 83.8 | 82.6 | 187 | 20 | 16 | 12 | 0 |
| slm-4b-sft | 235 | 11.5 | 12.3 | 18 | 18 | 182 | 1 | 16 |
| qwen3-4b-rag-auto | 235 | 87.9 | 87.0 | 199 | 15 | 11 | 10 | 0 |
| slm-4b-raft-v2-rag-k6 | 235 | 84.0 | 83.3 | 183 | 29 | 10 | 12 | 1 |
| slm-4b-raft-v3-rag | 235 | 84.7 | 83.6 | 187 | 24 | 14 | 10 | 0 |
| slm-4b-raft-v4-rag | 235 | 85.3 | 84.2 | 191 | 19 | 16 | 9 | 0 |

## Par categorie (score %)

| config | lore | gameplay | esport | patch | maps_modes | unanswerable |
|---|---|---|---|---|---|---|
| claude-opus | 72.5 (n=51) | 85.0 (n=50) | 26.7 (n=43) | 13.0 (n=50) | 72.0 (n=25) | 100.0 (n=16) |
| claude-sonnet | 57.8 (n=51) | 69.0 (n=50) | 12.8 (n=43) | 4.0 (n=50) | 56.0 (n=25) | 100.0 (n=16) |
| claude-sonnet-rag | 95.1 (n=51) | 100.0 (n=50) | 81.4 (n=43) | 92.0 (n=50) | 100.0 (n=25) | 100.0 (n=16) |
| claude-sonnet-web | 100.0 (n=7) | 100.0 (n=7) | 75.0 (n=10) | 66.0 (n=50) | n/a (n=0) | n/a (n=0) |
| qwen3-1.7b-base | 0.0 (n=51) | 1.0 (n=50) | 3.5 (n=43) | 0.0 (n=50) | 6.0 (n=25) | 12.5 (n=16) |
| qwen3-1.7b-rag | 83.3 (n=51) | 86.0 (n=50) | 67.4 (n=43) | 75.0 (n=50) | 100.0 (n=25) | 81.2 (n=16) |
| qwen3-14b | 18.6 (n=51) | 9.0 (n=50) | 2.3 (n=43) | 8.0 (n=50) | 18.0 (n=25) | 37.5 (n=16) |
| qwen3-14b-rag | 95.1 (n=51) | 94.0 (n=50) | 79.1 (n=43) | 85.0 (n=50) | 100.0 (n=25) | 100.0 (n=16) |
| qwen3-4b-base | 2.9 (n=51) | 3.0 (n=50) | 3.5 (n=43) | 1.0 (n=50) | 8.0 (n=25) | 25.0 (n=16) |
| qwen3-4b-rag | 92.2 (n=51) | 89.0 (n=50) | 72.1 (n=43) | 81.0 (n=50) | 98.0 (n=25) | 100.0 (n=16) |
| slm-1.7b-raft-rag | 79.4 (n=51) | 85.0 (n=50) | 66.3 (n=43) | 78.0 (n=50) | 96.0 (n=25) | 93.8 (n=16) |
| slm-4b-cpt-sft | 18.6 (n=51) | 26.0 (n=50) | 7.0 (n=43) | 6.0 (n=50) | 26.0 (n=25) | 0.0 (n=16) |
| slm-4b-raft-rag | 84.3 (n=51) | 87.0 (n=50) | 68.6 (n=43) | 81.0 (n=50) | 96.0 (n=25) | 100.0 (n=16) |
| slm-4b-raft-v2-rag | 84.3 (n=51) | 87.0 (n=50) | 68.6 (n=43) | 82.0 (n=50) | 96.0 (n=25) | 100.0 (n=16) |
| slm-4b-sft | 14.7 (n=51) | 19.0 (n=50) | 8.1 (n=43) | 4.0 (n=50) | 18.0 (n=25) | 0.0 (n=16) |
| qwen3-4b-rag-auto | 92.2 (n=51) | 88.0 (n=50) | 74.4 (n=43) | 85.0 (n=50) | 100.0 (n=25) | 100.0 (n=16) |
| slm-4b-raft-v2-rag-k6 | 89.2 (n=51) | 85.0 (n=50) | 69.8 (n=43) | 82.0 (n=50) | 94.0 (n=25) | 93.8 (n=16) |
| slm-4b-raft-v3-rag | 88.2 (n=51) | 87.0 (n=50) | 67.4 (n=43) | 82.0 (n=50) | 98.0 (n=25) | 100.0 (n=16) |
| slm-4b-raft-v4-rag | 85.3 (n=51) | 88.0 (n=50) | 76.7 (n=43) | 79.0 (n=50) | 98.0 (n=25) | 100.0 (n=16) |

## Temporel / couvert (questions repondables, score %)

| config | temporel | non temporel | couvert | non couvert |
|---|---|---|---|---|
| claude-opus | 15.5 (n=74) | 71.7 (n=145) | 58.8 (n=164) | 34.5 (n=55) |
| claude-sonnet | 5.4 (n=74) | 56.2 (n=145) | 46.6 (n=164) | 16.4 (n=55) |
| claude-sonnet-rag | 92.6 (n=74) | 93.8 (n=145) | 95.1 (n=164) | 88.2 (n=55) |
| claude-sonnet-web | 73.6 (n=74) | n/a (n=0) | 71.7 (n=53) | 78.6 (n=21) |
| qwen3-1.7b-base | 0.0 (n=74) | 2.4 (n=145) | 1.5 (n=164) | 1.8 (n=55) |
| qwen3-1.7b-rag | 75.0 (n=74) | 83.8 (n=145) | 82.0 (n=164) | 77.3 (n=55) |
| qwen3-14b | 6.1 (n=74) | 13.1 (n=145) | 11.6 (n=164) | 8.2 (n=55) |
| qwen3-14b-rag | 87.2 (n=74) | 91.4 (n=145) | 91.8 (n=164) | 84.5 (n=55) |
| qwen3-4b-base | 2.0 (n=74) | 3.8 (n=145) | 3.4 (n=164) | 2.7 (n=55) |
| qwen3-4b-rag | 79.7 (n=74) | 88.6 (n=145) | 87.2 (n=164) | 80.9 (n=55) |
| slm-1.7b-raft-rag | 77.7 (n=74) | 80.7 (n=145) | 81.4 (n=164) | 74.5 (n=55) |
| slm-4b-cpt-sft | 6.8 (n=74) | 20.7 (n=145) | 18.3 (n=164) | 9.1 (n=55) |
| slm-4b-raft-rag | 79.7 (n=74) | 83.8 (n=145) | 85.1 (n=164) | 74.5 (n=55) |
| slm-4b-raft-v2-rag | 81.8 (n=74) | 83.1 (n=145) | 85.4 (n=164) | 74.5 (n=55) |
| slm-4b-sft | 3.4 (n=74) | 16.9 (n=145) | 15.2 (n=164) | 3.6 (n=55) |
| qwen3-4b-rag-auto | 83.1 (n=74) | 89.0 (n=145) | 87.8 (n=164) | 84.5 (n=55) |
| slm-4b-raft-v2-rag-k6 | 83.1 (n=74) | 83.4 (n=145) | 86.3 (n=164) | 74.5 (n=55) |
| slm-4b-raft-v3-rag | 80.4 (n=74) | 85.2 (n=145) | 86.6 (n=164) | 74.5 (n=55) |
| slm-4b-raft-v4-rag | 79.1 (n=74) | 86.9 (n=145) | 85.1 (n=164) | 81.8 (n=55) |

Couvert = fait du test retrouve dans le dataset d'entrainement (`data/dataset/test_coverage.jsonl`, heuristique indicative).

## Hallucination et abstention

| config | n unanswerable | taux d'hallucination % | n repondables | taux d'abstention % |
|---|---|---|---|---|
| claude-opus | 16 | 0.0 | 219 | 32.4 |
| claude-sonnet | 16 | 0.0 | 219 | 43.8 |
| claude-sonnet-rag | 16 | 0.0 | 219 | 5.0 |
| claude-sonnet-web | 0 | n/a | 74 | 16.2 |
| qwen3-1.7b-base | 16 | 87.5 | 219 | 4.6 |
| qwen3-1.7b-rag | 16 | 18.8 | 219 | 1.8 |
| qwen3-14b | 16 | 62.5 | 219 | 7.8 |
| qwen3-14b-rag | 16 | 0.0 | 219 | 4.1 |
| qwen3-4b-base | 16 | 75.0 | 219 | 5.0 |
| qwen3-4b-rag | 16 | 0.0 | 219 | 3.7 |
| slm-1.7b-raft-rag | 16 | 6.2 | 219 | 3.7 |
| slm-4b-cpt-sft | 16 | 100.0 | 219 | 0.5 |
| slm-4b-raft-rag | 16 | 0.0 | 219 | 9.1 |
| slm-4b-raft-v2-rag | 16 | 0.0 | 219 | 5.5 |
| slm-4b-sft | 16 | 100.0 | 219 | 0.5 |
| qwen3-4b-rag-auto | 16 | 0.0 | 219 | 4.6 |
| slm-4b-raft-v2-rag-k6 | 16 | 6.2 | 219 | 5.5 |
| slm-4b-raft-v3-rag | 16 | 0.0 | 219 | 4.6 |
| slm-4b-raft-v4-rag | 16 | 0.0 | 219 | 4.1 |

## Performance

| config | latence p50 s | latence p95 s | ttft p50 s | tok/s median | VRAM Mo | cout/requete USD |
|---|---|---|---|---|---|---|
| claude-opus | 5.78 | 11.65 | 2.62 | 202.5 | n/a | 0.0148 |
| claude-sonnet | 5.62 | 11.52 | 3.25 | 390.4 | n/a | 0.0084 |
| claude-sonnet-rag | 3.14 | 5.11 | 1.69 | 264.4 | n/a | 0.0203 |
| claude-sonnet-web | 16.72 | 30.32 | 1.98 | 66.3 | n/a | 0.0336 |
| qwen3-1.7b-base | 0.17 | 0.34 | 0.04 | 414.2 | 2158 | 0.0000 |
| qwen3-1.7b-rag | 0.24 | 0.39 | 0.16 | 362.4 | 2158 | 0.0000 |
| qwen3-14b | 0.64 | 1.39 | 0.04 | 77.3 | 10468 | 0.0000 |
| qwen3-14b-rag | 1.24 | 1.89 | 0.87 | 74.6 | 10468 | 0.0000 |
| qwen3-4b-base | 0.28 | 0.57 | 0.04 | 211.1 | 3873 | 0.0000 |
| qwen3-4b-rag | 0.46 | 0.78 | 0.29 | 193.4 | 3873 | 0.0000 |
| slm-1.7b-raft-rag | 0.21 | 0.28 | 0.15 | 382.7 | 2158 | 0.0000 |
| slm-4b-cpt-sft | 0.12 | 0.20 | 0.03 | 226.5 | 3873 | 0.0000 |
| slm-4b-raft-rag | 0.38 | 0.50 | 0.27 | 204.1 | 3873 | 0.0000 |
| slm-4b-raft-v2-rag | 0.37 | 0.51 | 0.27 | 207.4 | 3873 | 0.0000 |
| slm-4b-sft | 0.12 | 0.20 | 0.03 | 227.4 | 3873 | 0.0000 |
| qwen3-4b-rag-auto | 0.40 | 0.72 | 0.26 | 204.2 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-k6 | 0.50 | 0.79 | 0.39 | 198.1 | 3878 | 0.0000 |
| slm-4b-raft-v3-rag | 0.38 | 0.51 | 0.26 | 204.3 | 3878 | 0.0000 |
| slm-4b-raft-v4-rag | 0.37 | 0.51 | 0.26 | 204.7 | 3878 | 0.0000 |

Local : cout = 0. Claude : cout = equivalent API (abonnement, pas une depense reelle). Pour `claude_cli`, tok/s et latence sont indicatifs (reseau inclus, tokens de reflexion inclus). VRAM lue via Ollama (`/api/ps`), pas `nvidia-smi`.

## Accord juge / verification manuelle

Echantillon verifie : 111 reponses ; accord 100.0 % ; kappa de Cohen 1.00.

## Cout de mise a jour (Saison 5)

A renseigner manuellement (pages re-scrapees, minutes de generation et d'entrainement).
