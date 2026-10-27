# Provenance des erreurs des bras + RAG

Erreurs = questions repondables non jugees `correct` (partielles, incorrectes, abstentions). Pour chacune, `qwen3.6:35b-a3b` verifie si les passages recus contenaient la reponse de reference (`bench/errors.py`, prompt de verification des refus RAFT). Verification automatique, indicative.

| config | erreurs | recherche (reponse absente des passages) | partiel | lecture (reponse presente) | |
|---|---|---|---|---|---|
| qwen3-4b-rag | 46 | 14 (30 %) | 2 (4 %) | 29 (63 %) | 1 non verifiees |
| qwen3-1.7b-rag | 54 | 14 (26 %) | 2 (4 %) | 37 (69 %) | 1 non verifiees |
| qwen3-14b-rag | 33 | 13 (39 %) | 2 (6 %) | 18 (55 %) | |
| claude-sonnet-rag | 21 | 12 (57 %) | 1 (5 %) | 8 (38 %) | |
| slm-4b-raft-rag | 48 | 13 (27 %) | 3 (6 %) | 31 (65 %) | 1 non verifiees |
| slm-4b-raft-v2-rag | 48 | 13 (27 %) | 2 (4 %) | 32 (67 %) | 1 non verifiees |
| slm-1.7b-raft-rag | 56 | 13 (23 %) | 2 (4 %) | 40 (71 %) | 1 non verifiees |
