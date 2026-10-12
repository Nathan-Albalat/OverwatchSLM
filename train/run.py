"""Entrainement QLoRA (Unsloth + TRL). A executer dans WSL (voir CLAUDE.md)."""
import json
import time

from train.common import TRAIN_DIR, get_run, resolve


def train(run_name, resume=False, max_steps=None, limit=None, tag=None, data=None, val_data=None,
          init_from=None, save_every=None, eval_every=None):
    import unsloth  # noqa: F401  (doit etre importe avant trl/transformers)
    import torch
    from transformers import TrainerCallback
    from transformers.trainer_utils import get_last_checkpoint
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel
    from train.data import build_dataset, describe_example

    cfg = get_run(run_name, tag)
    rd = cfg["run_dir"]
    rd.mkdir(parents=True, exist_ok=True)
    ckpt_dir = rd / "checkpoints"
    stop_file = rd / "STOP"
    if stop_file.exists():
        stop_file.unlink()
        print("STOP supprime (reprise)")
    stage = cfg["stage"]
    data = data or cfg["data"]
    val_data = val_data or cfg.get("val_data")
    init_from = init_from or cfg.get("init_from")
    maxlen = cfg["max_seq_length"]
    t_start = time.time()

    # --- modele ---
    t0 = time.time()
    if init_from:
        adapter = TRAIN_DIR / init_from / "adapter"
        if not adapter.exists():
            raise SystemExit(f"adapter introuvable pour init_from : {adapter}")
        print(f"chargement de l'adapter {adapter}")
        model, tok = FastLanguageModel.from_pretrained(str(adapter), max_seq_length=maxlen,
                                                       load_in_4bit=cfg["load_in_4bit"])
    else:
        model, tok = FastLanguageModel.from_pretrained(cfg["model"], max_seq_length=maxlen,
                                                       load_in_4bit=cfg["load_in_4bit"])
        model = FastLanguageModel.get_peft_model(
            model, r=cfg["lora_r"], lora_alpha=cfg["lora_alpha"], lora_dropout=cfg["lora_dropout"],
            target_modules=cfg["target_modules"], use_gradient_checkpointing="unsloth", random_state=cfg["seed"])
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"parametres entrainables : {n_train / 1e6:.1f} M")
    if n_train == 0:
        raise SystemExit("aucun parametre entrainable")
    t_load = time.time() - t0

    # --- donnees ---
    t0 = time.time()
    ds, dstats = build_dataset(tok, data, stage, maxlen, limit=limit, seed=cfg["seed"])
    vds, vstats = (None, None)
    if val_data and resolve(val_data).exists():
        vds, vstats = build_dataset(tok, val_data, stage, maxlen, sample=cfg["eval_samples"], seed=cfg["seed"])
    t_data = time.time() - t0
    print(f"train : {dstats} ; val : {vstats}")

    class StopCb(TrainerCallback):
        def on_step_end(self, args, state, control, **kw):
            if stop_file.exists():
                print(f"STOP detecte au pas {state.global_step} : sauvegarde puis arret", flush=True)
                control.should_save = True
                control.should_training_stop = True

    eval_every = eval_every or cfg["eval_every"]
    args = SFTConfig(
        output_dir=str(ckpt_dir), per_device_train_batch_size=cfg["batch"], per_device_eval_batch_size=cfg["batch"],
        gradient_accumulation_steps=cfg["grad_accum"], num_train_epochs=cfg["epochs"],
        max_steps=max_steps if max_steps else -1, learning_rate=cfg["lr"], lr_scheduler_type=cfg["lr_scheduler"],
        warmup_ratio=cfg["warmup_ratio"], optim=cfg["optim"], bf16=True, seed=cfg["seed"], logging_steps=10,
        eval_strategy="steps" if vds is not None else "no", eval_steps=eval_every,
        save_strategy="steps", save_steps=save_every or cfg["save_every"], save_total_limit=cfg["save_total_limit"],
        max_length=maxlen, packing=cfg["packing"], report_to="none",
        **({"dataset_text_field": "text"} if stage == "cpt" else {}))
    trainer = SFTTrainer(model=model, processing_class=tok, train_dataset=ds, eval_dataset=vds, args=args,
                         callbacks=[StopCb()])
    describe_example(tok, ds, trainer.train_dataset)

    last = get_last_checkpoint(str(ckpt_dir)) if resume and ckpt_dir.exists() else None
    if resume:
        print(f"reprise depuis {last}" if last else "aucun checkpoint : demarrage a zero")
    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    res = trainer.train(resume_from_checkpoint=last)
    t_train = time.time() - t0
    stopped = stop_file.exists()
    peak = torch.cuda.max_memory_allocated() / 1e9

    # --- fin ---
    model.save_pretrained(str(rd / "adapter"))
    tok.save_pretrained(str(rd / "adapter"))
    val_loss = None
    if vds is not None and not stopped:
        t0 = time.time()
        val_loss = trainer.evaluate().get("eval_loss")
        t_eval = time.time() - t0
    else:
        t_eval = 0.0
    logs = [h for h in trainer.state.log_history if "loss" in h]
    st = trainer.state
    # avec packing, une sequence du trainer regroupe plusieurs exemples : on ramene tout en exemples d origine
    n_seqs = len(trainer.train_dataset)
    frac = st.global_step * cfg["batch"] * cfg["grad_accum"] / n_seqs if n_seqs else 0
    n_seen = round(frac * dstats["kept"])
    prev = {}
    if (rd / "train_stats.json").exists() and resume:
        prev = json.loads((rd / "train_stats.json").read_text(encoding="utf-8"))
    train_s = t_train + prev.get("train_seconds", 0.0)
    stats = {
        "run": cfg["run_name"], "stage": stage, "model": cfg["model"], "init_from": init_from,
        "hyperparams": {k: cfg[k] for k in ("max_seq_length", "load_in_4bit", "lora_r", "lora_alpha", "lora_dropout",
                                            "lr", "lr_scheduler", "warmup_ratio", "optim", "seed", "batch",
                                            "grad_accum", "epochs", "packing")},
        "data": str(data), "val_data": str(val_data) if vds is not None else None,
        "train_examples": dstats["kept"], "val_examples": vstats["kept"] if vstats else 0,
        "dropped_too_long": dstats["dropped_too_long"],
        "dataset_tokens_total": dstats["total_tokens"], "dataset_tokens_completion": dstats["completion_tokens"],
        "steps": st.global_step, "max_steps_arg": max_steps, "stopped_by_file": stopped,
        "examples_seen": n_seen,
        "tokens_seen_total_est": round(dstats["total_tokens"] * frac),
        "tokens_seen_completion_est": round(dstats["completion_tokens"] * frac),
        "seconds": {"load_model": round(t_load, 1), "prepare_data": round(t_data, 1), "eval_final": round(t_eval, 1),
                    "total_session": round(time.time() - t_start, 1)},
        "train_seconds": round(train_s, 1),
        "s_per_example": round(train_s / n_seen, 3) if n_seen else None,
        "tokens_per_s": round(dstats["total_tokens"] * frac / train_s) if train_s and frac else None,
        "peak_vram_gb": round(max(peak, prev.get("peak_vram_gb", 0)), 2),
        "train_loss_final": logs[-1]["loss"] if logs else None,
        "train_loss_mean": round(res.training_loss, 4),
        "val_loss_final": val_loss,
        "resumed_from": last,
    }
    (rd / "train_stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stats, indent=1, ensure_ascii=False))
    print("arret propre (STOP)" if stopped else "termine", "- adapter :", rd / "adapter")
    return stats
