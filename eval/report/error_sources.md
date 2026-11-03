# Provenance des erreurs des bras + RAG

Erreurs = questions repondables non jugees `correct` (partielles, incorrectes, abstentions). Pour chacune, `qwen3.6:35b-a3b` verifie si les passages recus contenaient la reponse de reference (`bench/errors.py`, prompt de verification des refus RAFT). Verification automatique, indicative.

| config | erreurs | recherche (reponse absente des passages) | partiel | lecture (reponse presente) | |
|---|---|---|---|---|---|
| claude-sonnet-rag | 18 | 11 (61 %) | 1 (6 %) | 6 (33 %) | |
| qwen3-14b-rag | 28 | 12 (43 %) | 2 (7 %) | 14 (50 %) | |
| qwen3-4b-rag | 41 | 13 (32 %) | 2 (5 %) | 25 (61 %) | 1 non verifiees |
| slm-4b-raft-rag | 48 | 13 (27 %) | 3 (6 %) | 31 (65 %) | 1 non verifiees |
| qwen3-4b-rag-auto | 36 | 13 (36 %) | 2 (6 %) | 20 (56 %) | 1 non verifiees |
| slm-4b-raft-v2-rag | 48 | 13 (27 %) | 2 (4 %) | 32 (67 %) | 1 non verifiees |
| slm-4b-raft-v3-rag | 48 | 13 (27 %) | 2 (4 %) | 32 (67 %) | 1 non verifiees |
| slm-4b-raft-v4-rag | 44 | 13 (30 %) | 2 (5 %) | 28 (64 %) | 1 non verifiees |
| qwen3-1.7b-rag | 49 | 13 (27 %) | 2 (4 %) | 33 (67 %) | 1 non verifiees |
| slm-1.7b-raft-rag | 56 | 13 (23 %) | 2 (4 %) | 40 (71 %) | 1 non verifiees |
