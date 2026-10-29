# Rapport du banc d'evaluation OW-SLM

Score : correct = 1, partial = 0.5, le reste = 0. Jeu de test fige : `eval/test_set.jsonl`.
Sources du corpus : Overwatch Fandom wiki (CC-BY-SA) et Liquipedia Overwatch (CC-BY-SA 3.0, attribution obligatoire).

## Exactitude globale

| config | n | score global % | score repondables % | correct | partial | incorrect | abstained | hallucinated |
|---|---|---|---|---|---|---|---|---|
| qwen3-4b-rag | 327 | 83.3 | 81.8 | 262 | 21 | 26 | 18 | 0 |
| qwen3-4b-rag-auto | 327 | 82.4 | 80.8 | 259 | 21 | 30 | 17 | 0 |
| qwen3-4b-rag-rw | 327 | 80.3 | 78.5 | 252 | 21 | 36 | 18 | 0 |
| slm-1.7b-raft-rag | 327 | 83.8 | 82.3 | 264 | 20 | 30 | 13 | 0 |
| slm-4b-raft-rag | 327 | 80.3 | 78.5 | 255 | 15 | 17 | 40 | 0 |
| slm-4b-raft-v2-rag | 327 | 87.2 | 86.0 | 279 | 12 | 21 | 15 | 0 |
| slm-4b-raft-v2-rag-ent | 327 | 86.2 | 85.0 | 275 | 14 | 20 | 18 | 0 |
| slm-4b-raft-v2-rag-ent5 | 327 | 86.2 | 85.0 | 274 | 16 | 21 | 16 | 0 |
| slm-4b-raft-v2-rag-k6 | 327 | 88.5 | 87.5 | 281 | 17 | 17 | 12 | 0 |
| slm-4b-raft-v2-rag-mpp3 | 327 | 87.5 | 86.3 | 279 | 14 | 17 | 17 | 0 |
| slm-4b-raft-v2-rag-recent | 327 | 86.9 | 85.7 | 277 | 14 | 20 | 16 | 0 |
| slm-4b-raft-v2-rag-rw | 327 | 84.7 | 83.3 | 270 | 14 | 21 | 22 | 0 |
| slm-4b-raft-v3-rag | 327 | 87.3 | 86.2 | 278 | 15 | 19 | 15 | 0 |
| slm-4b-raft-v4-rag | 327 | 85.3 | 84.0 | 272 | 14 | 23 | 18 | 0 |

## Par categorie (score %)

| config | lore | gameplay | esport | patch | maps_modes | unanswerable |
|---|---|---|---|---|---|---|
| qwen3-4b-rag | 78.0 (n=82) | 65.0 (n=10) | 86.5 (n=163) | 74.0 (n=25) | 77.5 (n=20) | 100.0 (n=27) |
| qwen3-4b-rag-auto | 77.4 (n=82) | 65.0 (n=10) | 84.7 (n=163) | 78.0 (n=25) | 75.0 (n=20) | 100.0 (n=27) |
| qwen3-4b-rag-rw | 73.8 (n=82) | 65.0 (n=10) | 82.2 (n=163) | 76.0 (n=25) | 77.5 (n=20) | 100.0 (n=27) |
| slm-1.7b-raft-rag | 78.0 (n=82) | 70.0 (n=10) | 89.6 (n=163) | 62.0 (n=25) | 72.5 (n=20) | 100.0 (n=27) |
| slm-4b-raft-rag | 68.3 (n=82) | 65.0 (n=10) | 87.7 (n=163) | 66.0 (n=25) | 67.5 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v2-rag | 80.5 (n=82) | 60.0 (n=10) | 92.9 (n=163) | 76.0 (n=25) | 77.5 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v2-rag-ent | 78.0 (n=82) | 60.0 (n=10) | 92.6 (n=163) | 76.0 (n=25) | 75.0 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v2-rag-ent5 | 78.7 (n=82) | 60.0 (n=10) | 92.6 (n=163) | 74.0 (n=25) | 75.0 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v2-rag-k6 | 82.3 (n=82) | 65.0 (n=10) | 92.6 (n=163) | 82.0 (n=25) | 85.0 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v2-rag-mpp3 | 79.3 (n=82) | 85.0 (n=10) | 92.6 (n=163) | 76.0 (n=25) | 77.5 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v2-rag-recent | 79.9 (n=82) | 60.0 (n=10) | 92.6 (n=163) | 76.0 (n=25) | 77.5 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v2-rag-rw | 73.2 (n=82) | 55.0 (n=10) | 92.0 (n=163) | 76.0 (n=25) | 77.5 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v3-rag | 80.5 (n=82) | 65.0 (n=10) | 94.8 (n=163) | 74.0 (n=25) | 65.0 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v4-rag | 79.9 (n=82) | 60.0 (n=10) | 90.2 (n=163) | 70.0 (n=25) | 80.0 (n=20) | 100.0 (n=27) |

## Temporel / couvert (questions repondables, score %)

| config | temporel | non temporel | couvert | non couvert |
|---|---|---|---|---|
| qwen3-4b-rag | n/a (n=0) | 81.8 (n=300) | n/a | n/a |
| qwen3-4b-rag-auto | n/a (n=0) | 80.8 (n=300) | n/a | n/a |
| qwen3-4b-rag-rw | n/a (n=0) | 78.5 (n=300) | n/a | n/a |
| slm-1.7b-raft-rag | n/a (n=0) | 82.3 (n=300) | n/a | n/a |
| slm-4b-raft-rag | n/a (n=0) | 78.5 (n=300) | n/a | n/a |
| slm-4b-raft-v2-rag | n/a (n=0) | 86.0 (n=300) | n/a | n/a |
| slm-4b-raft-v2-rag-ent | n/a (n=0) | 85.0 (n=300) | n/a | n/a |
| slm-4b-raft-v2-rag-ent5 | n/a (n=0) | 85.0 (n=300) | n/a | n/a |
| slm-4b-raft-v2-rag-k6 | n/a (n=0) | 87.5 (n=300) | n/a | n/a |
| slm-4b-raft-v2-rag-mpp3 | n/a (n=0) | 86.3 (n=300) | n/a | n/a |
| slm-4b-raft-v2-rag-recent | n/a (n=0) | 85.7 (n=300) | n/a | n/a |
| slm-4b-raft-v2-rag-rw | n/a (n=0) | 83.3 (n=300) | n/a | n/a |
| slm-4b-raft-v3-rag | n/a (n=0) | 86.2 (n=300) | n/a | n/a |
| slm-4b-raft-v4-rag | n/a (n=0) | 84.0 (n=300) | n/a | n/a |

Couvert = fait du test retrouve dans le dataset d'entrainement (`data/dataset/test_coverage.jsonl`, heuristique indicative). Fichier absent : colonnes n/a.

## Hallucination et abstention

| config | n unanswerable | taux d'hallucination % | n repondables | taux d'abstention % |
|---|---|---|---|---|
| qwen3-4b-rag | 27 | 0.0 | 300 | 6.0 |
| qwen3-4b-rag-auto | 27 | 0.0 | 300 | 5.7 |
| qwen3-4b-rag-rw | 27 | 0.0 | 300 | 6.0 |
| slm-1.7b-raft-rag | 27 | 0.0 | 300 | 4.3 |
| slm-4b-raft-rag | 27 | 0.0 | 300 | 13.3 |
| slm-4b-raft-v2-rag | 27 | 0.0 | 300 | 5.0 |
| slm-4b-raft-v2-rag-ent | 27 | 0.0 | 300 | 6.0 |
| slm-4b-raft-v2-rag-ent5 | 27 | 0.0 | 300 | 5.3 |
| slm-4b-raft-v2-rag-k6 | 27 | 0.0 | 300 | 4.0 |
| slm-4b-raft-v2-rag-mpp3 | 27 | 0.0 | 300 | 5.7 |
| slm-4b-raft-v2-rag-recent | 27 | 0.0 | 300 | 5.3 |
| slm-4b-raft-v2-rag-rw | 27 | 0.0 | 300 | 7.3 |
| slm-4b-raft-v3-rag | 27 | 0.0 | 300 | 5.0 |
| slm-4b-raft-v4-rag | 27 | 0.0 | 300 | 6.0 |

## Performance

| config | latence p50 s | latence p95 s | ttft p50 s | tok/s median | VRAM Mo | cout/requete USD |
|---|---|---|---|---|---|---|
| qwen3-4b-rag | 0.42 | 0.81 | 0.23 | 204.8 | 3873 | 0.0000 |
| qwen3-4b-rag-auto | 1.43 | 3.40 | 0.71 | 42.9 | 3878 | 0.0000 |
| qwen3-4b-rag-rw | 0.42 | 0.83 | 0.21 | 192.6 | 3878 | 0.0000 |
| slm-1.7b-raft-rag | 0.20 | 0.30 | 0.14 | 384.1 | 2158 | 0.0000 |
| slm-4b-raft-rag | 0.34 | 0.48 | 0.24 | 205.4 | 3873 | 0.0000 |
| slm-4b-raft-v2-rag | 0.34 | 0.48 | 0.23 | 208.9 | 3873 | 0.0000 |
| slm-4b-raft-v2-rag-ent | 0.34 | 0.49 | 0.23 | 205.3 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-ent5 | 0.35 | 0.55 | 0.24 | 205.4 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-k6 | 0.76 | 1.08 | 0.55 | 99.4 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-mpp3 | 0.57 | 0.84 | 0.35 | 98.2 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-recent | 30.49 | 43.29 | 30.35 | 186.9 | 3878 | 0.0000 |
| slm-4b-raft-v2-rag-rw | 0.32 | 0.48 | 0.21 | 193.3 | 3878 | 0.0000 |
| slm-4b-raft-v3-rag | 0.34 | 0.49 | 0.23 | 199.1 | 3878 | 0.0000 |
| slm-4b-raft-v4-rag | 0.33 | 0.47 | 0.22 | 206.3 | 3878 | 0.0000 |

Local : cout = 0. Claude : cout = equivalent API (abonnement, pas une depense reelle). Pour `claude_cli`, tok/s et latence sont indicatifs (reseau inclus, tokens de reflexion inclus). VRAM lue via Ollama (`/api/ps`), pas `nvidia-smi`.

## Accord juge / verification manuelle

Pas encore de verification manuelle (`ow-bench review-export`, puis remplir `human_verdict`).

## Cout de mise a jour (Saison 5)

A renseigner manuellement (pages re-scrapees, minutes de generation et d'entrainement).
