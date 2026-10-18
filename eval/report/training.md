# Entrainements QLoRA (Unsloth + TRL)

Genere par `python -m train.cli summary` a partir de `data/train/*/train_stats.json`.

| run | modele | etape | exemples | ecartes (trop longs) | pas | tokens vus (total / reponse) | temps (min) | s/ex | tok/s | VRAM pic (Go) | loss train | loss val |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-1.7b-raft | Qwen3-1.7B | raft | 14072 | 0 | 880 | 27789778 / 336805 | 74.7 | 0.318 | 6198 | 11.46 | 0.346 | 0.337 |
| qwen3-4b-cpt | Qwen3-4B | cpt | 12360 | 0 | 84 | 5451173 / 5451173 | 30.2 | 0.145 | 3013 | 6.81 | 2.169 | - |
| qwen3-4b-cpt-sft | Qwen3-4B | sft (init qwen3-4b-cpt) | 102160 | 0 | 350 | 22464641 / 4878182 | 123.5 | 0.036 | 3032 | 16.10 | 1.012 | 1.059 |
| qwen3-4b-raft | Qwen3-4B | raft | 14250 | 0 | 891 | 28104961 / 329337 | 201.8 | 0.849 | 2322 | 13.85 | 0.246 | 0.240 |
| qwen3-4b-raft-v2 | Qwen3-4B | raft | 14072 | 0 | 880 | 27789778 / 336805 | 208.8 | 0.890 | 2218 | 13.84 | 0.278 | 0.275 |
| qwen3-4b-sft | Qwen3-4B | sft | 102160 | 0 | 350 | 22464641 / 4878182 | 124.5 | 0.036 | 3007 | 16.10 | 1.029 | 1.068 |

Hyperparametres communs : LoRA r=32 alpha=32 sur 7 modules, batch 4 x accumulation 4, AdamW 8 bits, cosine, bf16.
Les runs suffixes `-smoke` sont des tests de validation du code (quelques pas), pas des entrainements complets.
