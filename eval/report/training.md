# Entrainements QLoRA (Unsloth + TRL)

Genere par `python -m train.cli summary` a partir de `data/train/*/train_stats.json`.

| run | modele | etape | exemples | ecartes (trop longs) | pas | tokens vus (total / reponse) | temps (min) | s/ex | tok/s | VRAM pic (Go) | loss train | loss val |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-4b-raft | Qwen3-4B | raft | 14250 | 0 | 891 | 28104961 / 329337 | 201.8 | 0.849 | 2322 | 13.85 | 0.246 | 0.240 |

Hyperparametres communs : LoRA r=32 alpha=32 sur 7 modules, batch 4 x accumulation 4, AdamW 8 bits, cosine, bf16.
Les runs suffixes `-smoke` sont des tests de validation du code (quelques pas), pas des entrainements complets.
