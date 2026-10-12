"""Donnees d'entrainement : format chat -> (prompt, completion) identique a l'inference Ollama think:false."""
import json
import random

from train.common import resolve


def read_jsonl(path):
    with open(resolve(path), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def to_prompt_completion(tok, messages):
    """prompt = gabarit chat jusqu'a `<|im_start|>assistant\n<think>\n\n</think>\n\n` ; completion = reponse + <|im_end|>."""
    assert messages[-1]["role"] == "assistant"
    prompt = tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    return prompt, messages[-1]["content"].strip() + "<|im_end|>"


def n_tokens(tok, texts):
    return [len(x) for x in tok(texts, add_special_tokens=False)["input_ids"]]


def build_dataset(tok, path, stage, max_len, limit=None, sample=None, seed=0):
    """Retourne (Dataset, stats). Exemples plus longs que max_len ecartes (jamais tronques).
    `limit` : sous-echantillon deterministe de l'entrainement ; `sample` idem pour la val."""
    from datasets import Dataset
    rows = read_jsonl(path)
    n_read = len(rows)
    n = limit if limit else sample
    if n and len(rows) > n:
        rows = random.Random(seed).sample(rows, n)
    if stage == "cpt":
        texts = [r["text"].strip() + tok.eos_token for r in rows]
        lens = n_tokens(tok, texts)
        cols = {"text": texts}
        comp_lens = lens
    else:
        pc = [to_prompt_completion(tok, r["messages"]) for r in rows]
        prompts, comps = [p for p, _ in pc], [c for _, c in pc]
        pl, comp_lens = n_tokens(tok, prompts), n_tokens(tok, comps)
        lens = [a + b for a, b in zip(pl, comp_lens)]
        cols = {"prompt": prompts, "completion": comps}
    keep = [i for i, L in enumerate(lens) if L <= max_len]
    stats = {"read": n_read, "selected": len(rows), "kept": len(keep), "dropped_too_long": len(rows) - len(keep),
             "total_tokens": sum(lens[i] for i in keep),
             "completion_tokens": sum(comp_lens[i] for i in keep)}
    ds = Dataset.from_dict({k: [v[i] for i in keep] for k, v in cols.items()})
    return ds, stats


def describe_example(tok, ds, trainer_ds):
    """Affiche le premier exemple tel que vu par le trainer : texte decode et resume du masque."""
    ex = trainer_ds[0]
    ids = ex["input_ids"]
    mask = ex.get("completion_mask")
    if mask is None and "labels" in ex:  # TRL replie le masque dans `labels` (-100 = ignore)
        mask = [int(l != -100) for l in ex["labels"]]
    print("=" * 70)
    print("EXEMPLE DECODE (premiers 600 et derniers 250 caracteres)")
    txt = tok.decode(ids)
    print(txt[:600] + "\n[...]\n" + txt[-250:] if len(txt) > 850 else txt)
    print("-" * 70)
    print(f"tokens={len(ids)} ; <|im_end|> dans l'exemple : {txt.count('<|im_end|>')} (1 attendu par message) ; "
          f"fin = {ids[-3:]} -> {tok.decode(ids[-3:])!r}")
    if mask is not None:
        m = list(mask)
        first = m.index(1) if 1 in m else -1
        print(f"masque : {sum(m)} tokens de loss sur {len(m)} ; premier token de loss a {first} "
              f"-> {tok.decode(ids[first:first + 12])!r}")
        print(f"fin du prompt (non appris) = {tok.decode(ids[max(first - 8, 0):first])!r}")
    else:
        print("masque : aucun (loss sur tout le texte)")
    print("=" * 70, flush=True)
