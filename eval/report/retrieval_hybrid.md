# Qualite de la recherche (mode hybrid, 2026-10-08)

Index : 14737 documents (chunks + fiches de faits), embeddings : oui. Valeurs en %. Max 2 passages par page.

## Jeu de test (page attendue = champ `source`, hors unanswerable)

| ensemble | n | hit@1 | hit@3 | hit@5 | hit@10 |
|---|---|---|---|---|---|
| toutes categories | 211 | 75.4 | 87.2 | 90.0 | 93.8 |
| esport | 43 | 79.1 | 83.7 | 86.0 | 88.4 |
| gameplay | 50 | 86.0 | 98.0 | 100.0 | 100.0 |
| lore | 51 | 62.7 | 84.3 | 88.2 | 92.2 |
| maps_modes | 25 | 88.0 | 96.0 | 96.0 | 96.0 |
| patch | 42 | 66.7 | 76.2 | 81.0 | 92.9 |

0 questions sans source exploitable ignorees. Ratees a k=10 : T01, T02, T03, L07, L08, L33, L38, M15, E16, E17, E19, E32, E38

## Paires LLM du split val (1000 tirees, graine 0)

| ensemble | n | hit@1 | hit@3 | hit@5 | hit@10 |
|---|---|---|---|---|---|
| chunk exact | 1000 | 62.3 | 77.8 | 83.2 | 88.9 |
| page | 1000 | 66.1 | 80.7 | 86.3 | 91.6 |

Duree : 1 s
