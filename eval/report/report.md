# Rapport du banc d'evaluation OW-SLM

Score : correct = 1, partial = 0.5, le reste = 0. Jeu de test fige : `eval/test_set.jsonl`.
Sources du corpus : Overwatch Fandom wiki (CC-BY-SA) et Liquipedia Overwatch (CC-BY-SA 3.0, attribution obligatoire).

## Exactitude globale

| config | n | score global % | score repondables % | correct | partial | incorrect | abstained | hallucinated |
|---|---|---|---|---|---|---|---|---|
| claude-opus | 227 | 57.9 | 54.7 | 120 | 23 | 20 | 64 | 0 |
| claude-sonnet | 227 | 44.7 | 40.5 | 91 | 21 | 27 | 88 | 0 |
| claude-sonnet-rag | 227 | 94.1 | 93.6 | 210 | 7 | 0 | 10 | 0 |
| qwen3-1.7b-base | 227 | 2.4 | 1.7 | 3 | 5 | 194 | 11 | 14 |
| qwen3-1.7b-rag | 227 | 80.8 | 80.8 | 176 | 15 | 29 | 4 | 3 |
| qwen3-14b | 227 | 12.1 | 10.2 | 20 | 15 | 165 | 17 | 10 |
| qwen3-14b-rag | 227 | 90.7 | 90.0 | 200 | 12 | 7 | 8 | 0 |
| qwen3-4b-base | 227 | 4.8 | 3.3 | 5 | 12 | 186 | 12 | 12 |
| qwen3-4b-rag | 227 | 87.2 | 86.3 | 189 | 18 | 13 | 7 | 0 |

## Par categorie (score %)

| config | lore | gameplay | esport | patch | maps_modes | unanswerable |
|---|---|---|---|---|---|---|
| claude-opus | 72.5 (n=51) | 85.0 (n=50) | 26.7 (n=43) | 15.5 (n=42) | 72.0 (n=25) | 100.0 (n=16) |
| claude-sonnet | 57.8 (n=51) | 69.0 (n=50) | 12.8 (n=43) | 4.8 (n=42) | 56.0 (n=25) | 100.0 (n=16) |
| claude-sonnet-rag | 95.1 (n=51) | 100.0 (n=50) | 81.4 (n=43) | 92.9 (n=42) | 100.0 (n=25) | 100.0 (n=16) |
| qwen3-1.7b-base | 0.0 (n=51) | 1.0 (n=50) | 3.5 (n=43) | 0.0 (n=42) | 6.0 (n=25) | 12.5 (n=16) |
| qwen3-1.7b-rag | 83.3 (n=51) | 86.0 (n=50) | 67.4 (n=43) | 73.8 (n=42) | 100.0 (n=25) | 81.2 (n=16) |
| qwen3-14b | 18.6 (n=51) | 9.0 (n=50) | 2.3 (n=43) | 4.8 (n=42) | 18.0 (n=25) | 37.5 (n=16) |
| qwen3-14b-rag | 95.1 (n=51) | 94.0 (n=50) | 79.1 (n=43) | 84.5 (n=42) | 100.0 (n=25) | 100.0 (n=16) |
| qwen3-4b-base | 2.9 (n=51) | 3.0 (n=50) | 3.5 (n=43) | 1.2 (n=42) | 8.0 (n=25) | 25.0 (n=16) |
| qwen3-4b-rag | 92.2 (n=51) | 89.0 (n=50) | 72.1 (n=43) | 83.3 (n=42) | 98.0 (n=25) | 100.0 (n=16) |

## Temporel / couvert (questions repondables, score %)

| config | temporel | non temporel | couvert | non couvert |
|---|---|---|---|---|
| claude-opus | 17.4 (n=66) | 71.7 (n=145) | 61.6 (n=155) | 35.7 (n=56) |
| claude-sonnet | 6.1 (n=66) | 56.2 (n=145) | 49.0 (n=155) | 17.0 (n=56) |
| claude-sonnet-rag | 93.2 (n=66) | 93.8 (n=145) | 95.8 (n=155) | 87.5 (n=56) |
| qwen3-1.7b-base | 0.0 (n=66) | 2.4 (n=145) | 1.6 (n=155) | 1.8 (n=56) |
| qwen3-1.7b-rag | 74.2 (n=66) | 83.8 (n=145) | 81.9 (n=155) | 77.7 (n=56) |
| qwen3-14b | 3.8 (n=66) | 13.1 (n=145) | 11.3 (n=155) | 7.1 (n=56) |
| qwen3-14b-rag | 87.1 (n=66) | 91.4 (n=145) | 92.6 (n=155) | 83.0 (n=56) |
| qwen3-4b-base | 2.3 (n=66) | 3.8 (n=145) | 3.5 (n=155) | 2.7 (n=56) |
| qwen3-4b-rag | 81.1 (n=66) | 88.6 (n=145) | 87.7 (n=155) | 82.1 (n=56) |

Couvert = fait du test retrouve dans le dataset d'entrainement (`data/dataset/test_coverage.jsonl`, heuristique indicative).

## Hallucination et abstention

| config | n unanswerable | taux d'hallucination % | n repondables | taux d'abstention % |
|---|---|---|---|---|
| claude-opus | 16 | 0.0 | 211 | 30.3 |
| claude-sonnet | 16 | 0.0 | 211 | 41.7 |
| claude-sonnet-rag | 16 | 0.0 | 211 | 4.7 |
| qwen3-1.7b-base | 16 | 87.5 | 211 | 5.2 |
| qwen3-1.7b-rag | 16 | 18.8 | 211 | 1.9 |
| qwen3-14b | 16 | 62.5 | 211 | 8.1 |
| qwen3-14b-rag | 16 | 0.0 | 211 | 3.8 |
| qwen3-4b-base | 16 | 75.0 | 211 | 5.7 |
| qwen3-4b-rag | 16 | 0.0 | 211 | 3.3 |

## Performance

| config | latence p50 s | latence p95 s | ttft p50 s | tok/s median | VRAM Mo | cout/requete USD |
|---|---|---|---|---|---|---|
| claude-opus | 5.74 | 11.59 | 2.66 | 202.5 | n/a | 0.0147 |
| claude-sonnet | 5.70 | 11.55 | 3.26 | 395.7 | n/a | 0.0085 |
| claude-sonnet-rag | 3.14 | 5.08 | 1.68 | 264.4 | n/a | 0.0204 |
| qwen3-1.7b-base | 0.17 | 0.35 | 0.04 | 414.3 | 2158 | 0.0000 |
| qwen3-1.7b-rag | 0.24 | 0.40 | 0.16 | 362.9 | 2158 | 0.0000 |
| qwen3-14b | 0.64 | 1.40 | 0.04 | 77.3 | 10468 | 0.0000 |
| qwen3-14b-rag | 1.22 | 1.90 | 0.86 | 74.7 | 10468 | 0.0000 |
| qwen3-4b-base | 0.28 | 0.55 | 0.04 | 211.1 | 3873 | 0.0000 |
| qwen3-4b-rag | 0.45 | 0.78 | 0.29 | 193.5 | 3873 | 0.0000 |

Local : cout = 0. Claude : cout = equivalent API (abonnement, pas une depense reelle). Pour `claude_cli`, tok/s et latence sont indicatifs (reseau inclus, tokens de reflexion inclus). VRAM lue via Ollama (`/api/ps`), pas `nvidia-smi`.

## Accord juge / verification manuelle

Pas encore de verification manuelle (`ow-bench review-export`, puis remplir `human_verdict`).

## Cout de mise a jour (Saison 5)

A renseigner manuellement (pages re-scrapees, minutes de generation et d'entrainement).
