# Entrainements QLoRA (Unsloth + TRL)

Genere par `python -m train.cli summary` a partir de `data/train/*/train_stats.json`.

| run | modele | etape | exemples | ecartes (trop longs) | pas | tokens vus (total / reponse) | temps (min) | s/ex | tok/s | VRAM pic (Go) | loss train | loss val |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-1.7b-raft-smoke | Qwen3-1.7B | raft | 570 | 0 | 30 | 941327 / 11096 | 4.5 | 0.562 | 3488 | 11.26 | 0.521 | 0.416 |
| qwen3-4b-cpt-sft-smoke | Qwen3-4B | sft (init qwen3-4b-cpt-smoke) | 400 | 0 | 5 | 294793 / 64467 | 1.6 | 0.035 | 3135 | 14.28 | - | 1.793 |
| qwen3-4b-cpt-smoke | Qwen3-4B | cpt | 200 | 0 | 10 | 557640 / 557640 | 2.7 | 0.120 | 3489 | 6.78 | 2.754 | - |
| qwen3-4b-sft-smoke | Qwen3-4B | sft | 400 | 0 | 5 | 294793 / 64467 | 1.6 | 0.037 | 3016 | 14.28 | - | 1.934 |

Hyperparametres communs : LoRA r=32 alpha=32 sur 7 modules, batch 4 x accumulation 4, AdamW 8 bits, cosine, bf16.
Les runs suffixes `-smoke` sont des tests de validation du code (quelques pas), pas des entrainements complets.
