# Qualite de la recherche (mode dense, 2026-10-08)

Index : 14737 documents (chunks + fiches de faits), embeddings : oui. Valeurs en %. Max 2 passages par page.

## Jeu de test (page attendue = champ `source`, hors unanswerable)

| ensemble | n | hit@1 | hit@3 | hit@5 | hit@10 |
|---|---|---|---|---|---|
| toutes categories | 211 | 72.5 | 88.2 | 91.9 | 92.4 |
| esport | 43 | 74.4 | 83.7 | 90.7 | 90.7 |
| gameplay | 50 | 88.0 | 100.0 | 100.0 | 100.0 |
| lore | 51 | 66.7 | 84.3 | 94.1 | 96.1 |
| maps_modes | 25 | 84.0 | 96.0 | 96.0 | 96.0 |
| patch | 42 | 52.4 | 78.6 | 78.6 | 78.6 |

0 questions sans source exploitable ignorees. Ratees a k=10 : T01, T02, T03, T04, T32, T33, T34, T35, T36, L08, L38, M15, E26, E32, E38, E39

## Paires LLM du split val (1000 tirees, graine 0)

| ensemble | n | hit@1 | hit@3 | hit@5 | hit@10 |
|---|---|---|---|---|---|
| chunk exact | 1000 | 55.0 | 69.7 | 74.0 | 79.4 |
| page | 1000 | 60.1 | 74.2 | 79.0 | 84.5 |

Duree : 32 s
