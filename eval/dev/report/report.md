# Rapport du banc d'evaluation OW-SLM

Score : correct = 1, partial = 0.5, le reste = 0. Jeu de test fige : `eval/test_set.jsonl`.
Sources du corpus : Overwatch Fandom wiki (CC-BY-SA) et Liquipedia Overwatch (CC-BY-SA 3.0, attribution obligatoire).

## Exactitude globale

| config | n | score global % | score repondables % | correct | partial | incorrect | abstained | hallucinated |
|---|---|---|---|---|---|---|---|---|
| qwen3-4b-rag | 327 | 83.3 | 81.8 | 262 | 21 | 26 | 18 | 0 |
| slm-4b-raft-rag | 327 | 80.3 | 78.5 | 255 | 15 | 17 | 40 | 0 |
| slm-4b-raft-v2-rag | 327 | 87.2 | 86.0 | 279 | 12 | 21 | 15 | 0 |

## Par categorie (score %)

| config | lore | gameplay | esport | patch | maps_modes | unanswerable |
|---|---|---|---|---|---|---|
| qwen3-4b-rag | 78.0 (n=82) | 65.0 (n=10) | 86.5 (n=163) | 74.0 (n=25) | 77.5 (n=20) | 100.0 (n=27) |
| slm-4b-raft-rag | 68.3 (n=82) | 65.0 (n=10) | 87.7 (n=163) | 66.0 (n=25) | 67.5 (n=20) | 100.0 (n=27) |
| slm-4b-raft-v2-rag | 80.5 (n=82) | 60.0 (n=10) | 92.9 (n=163) | 76.0 (n=25) | 77.5 (n=20) | 100.0 (n=27) |

## Temporel / couvert (questions repondables, score %)

| config | temporel | non temporel | couvert | non couvert |
|---|---|---|---|---|
| qwen3-4b-rag | n/a (n=0) | 81.8 (n=300) | n/a | n/a |
| slm-4b-raft-rag | n/a (n=0) | 78.5 (n=300) | n/a | n/a |
| slm-4b-raft-v2-rag | n/a (n=0) | 86.0 (n=300) | n/a | n/a |

Couvert = fait du test retrouve dans le dataset d'entrainement (`data/dataset/test_coverage.jsonl`, heuristique indicative). Fichier absent : colonnes n/a.

## Hallucination et abstention

| config | n unanswerable | taux d'hallucination % | n repondables | taux d'abstention % |
|---|---|---|---|---|
| qwen3-4b-rag | 27 | 0.0 | 300 | 6.0 |
| slm-4b-raft-rag | 27 | 0.0 | 300 | 13.3 |
| slm-4b-raft-v2-rag | 27 | 0.0 | 300 | 5.0 |

## Performance

| config | latence p50 s | latence p95 s | ttft p50 s | tok/s median | VRAM Mo | cout/requete USD |
|---|---|---|---|---|---|---|
| qwen3-4b-rag | 0.42 | 0.81 | 0.23 | 204.8 | 3873 | 0.0000 |
| slm-4b-raft-rag | 0.34 | 0.48 | 0.24 | 205.4 | 3873 | 0.0000 |
| slm-4b-raft-v2-rag | 0.34 | 0.48 | 0.23 | 208.9 | 3873 | 0.0000 |

Local : cout = 0. Claude : cout = equivalent API (abonnement, pas une depense reelle). Pour `claude_cli`, tok/s et latence sont indicatifs (reseau inclus, tokens de reflexion inclus). VRAM lue via Ollama (`/api/ps`), pas `nvidia-smi`.

## Accord juge / verification manuelle

Pas encore de verification manuelle (`ow-bench review-export`, puis remplir `human_verdict`).

## Cout de mise a jour (Saison 5)

A renseigner manuellement (pages re-scrapees, minutes de generation et d'entrainement).
