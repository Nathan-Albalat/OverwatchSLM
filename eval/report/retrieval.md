# Qualite de la recherche (mode bm25, 2026-10-08)

Index : 14737 documents (chunks + fiches de faits), embeddings : non. Valeurs en %. Max 2 passages par page.

## Jeu de test (page attendue = champ `source`, hors unanswerable)

| ensemble | n | hit@1 | hit@3 | hit@5 | hit@10 |
|---|---|---|---|---|---|
| toutes categories | 211 | 43.1 | 71.1 | 78.2 | 87.7 |
| esport | 43 | 67.4 | 83.7 | 86.0 | 90.7 |
| gameplay | 50 | 44.0 | 80.0 | 86.0 | 92.0 |
| lore | 51 | 19.6 | 37.3 | 54.9 | 70.6 |
| maps_modes | 25 | 64.0 | 92.0 | 92.0 | 100.0 |
| patch | 42 | 33.3 | 76.2 | 81.0 | 92.9 |

0 questions sans source exploitable ignorees. Ratees a k=10 : G02, G15, G18, G33, T02, T03, T16, L01, L07, L10, L15, L16, L17, L19, L27, L30, L33, L35, L36, L37, L38, L48, E16, E17, E19, E38

## Paires LLM du split val (1000 tirees, graine 0)

| ensemble | n | hit@1 | hit@3 | hit@5 | hit@10 |
|---|---|---|---|---|---|
| chunk exact | 1000 | 61.4 | 80.5 | 88.0 | 92.8 |
| page | 1000 | 65.6 | 83.3 | 90.8 | 95.4 |

Duree : 0 s
