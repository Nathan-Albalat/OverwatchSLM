# Rapport du banc d'evaluation OW-SLM

Score : correct = 1, partial = 0.5, le reste = 0. Jeu de test fige : `eval/test_set.jsonl`.
Sources du corpus : Overwatch Fandom wiki (CC-BY-SA) et Liquipedia Overwatch (CC-BY-SA 3.0, attribution obligatoire).

## Exactitude globale

| config | n | score global % | score repondables % | correct | partial | incorrect | abstained | hallucinated |
|---|---|---|---|---|---|---|---|---|
| claude-opus | 227 | 57.9 | 54.7 | 120 | 23 | 20 | 64 | 0 |
| claude-sonnet | 227 | 44.7 | 40.5 | 91 | 21 | 27 | 88 | 0 |
| claude-sonnet-rag | 227 | 94.1 | 93.6 | 210 | 7 | 0 | 10 | 0 |

## Par categorie (score %)

| config | lore | gameplay | esport | patch | maps_modes | unanswerable |
|---|---|---|---|---|---|---|
| claude-opus | 72.5 (n=51) | 85.0 (n=50) | 26.7 (n=43) | 15.5 (n=42) | 72.0 (n=25) | 100.0 (n=16) |
| claude-sonnet | 57.8 (n=51) | 69.0 (n=50) | 12.8 (n=43) | 4.8 (n=42) | 56.0 (n=25) | 100.0 (n=16) |
| claude-sonnet-rag | 95.1 (n=51) | 100.0 (n=50) | 81.4 (n=43) | 92.9 (n=42) | 100.0 (n=25) | 100.0 (n=16) |

## Temporel / couvert (questions repondables, score %)

| config | temporel | non temporel | couvert | non couvert |
|---|---|---|---|---|
| claude-opus | 17.4 (n=66) | 71.7 (n=145) | 61.6 (n=155) | 35.7 (n=56) |
| claude-sonnet | 6.1 (n=66) | 56.2 (n=145) | 49.0 (n=155) | 17.0 (n=56) |
| claude-sonnet-rag | 93.2 (n=66) | 93.8 (n=145) | 95.8 (n=155) | 87.5 (n=56) |

Couvert = fait du test retrouve dans le dataset d'entrainement (`data/dataset/test_coverage.jsonl`, heuristique indicative).

## Hallucination et abstention

| config | n unanswerable | taux d'hallucination % | n repondables | taux d'abstention % |
|---|---|---|---|---|
| claude-opus | 16 | 0.0 | 211 | 30.3 |
| claude-sonnet | 16 | 0.0 | 211 | 41.7 |
| claude-sonnet-rag | 16 | 0.0 | 211 | 4.7 |

## Performance

| config | latence p50 s | latence p95 s | ttft p50 s | tok/s median | VRAM Mo | cout/requete USD |
|---|---|---|---|---|---|---|
| claude-opus | 5.74 | 11.59 | 2.66 | 202.5 | n/a | 0.0147 |
| claude-sonnet | 5.70 | 11.55 | 3.26 | 395.7 | n/a | 0.0085 |
| claude-sonnet-rag | 3.14 | 5.08 | 1.68 | 264.4 | n/a | 0.0204 |

Local : cout = 0. Claude : cout = equivalent API (abonnement, pas une depense reelle). Pour `claude_cli`, tok/s et latence sont indicatifs (reseau inclus, tokens de reflexion inclus). VRAM lue via Ollama (`/api/ps`), pas `nvidia-smi`.

## Accord juge / verification manuelle

Pas encore de verification manuelle (`ow-bench review-export`, puis remplir `human_verdict`).

## Cout de mise a jour (Saison 5)

A renseigner manuellement (pages re-scrapees, minutes de generation et d'entrainement).
