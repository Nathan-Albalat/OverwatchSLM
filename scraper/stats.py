import json
from collections import Counter

from .config import CLEAN, DATA, MIN_WORDS, RAW


def _count_lines(path):
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def run():
    result = {}
    for src in ("fandom", "liquipedia"):
        path = CLEAN / f"{src}.jsonl"
        if not path.exists():
            continue
        n = words = 0
        cats = Counter()
        lengths = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                w = len(r["text"].split())
                n += 1
                words += w
                cats.update(r.get("categories", []))
                lengths.append((w, r["title"]))
        raw_n = _count_lines(RAW / src / "pages.jsonl")
        lengths.sort(reverse=True)
        result[src] = {
            "pages_raw": raw_n, "pages": n, "pages_filtered_out": raw_n - n,
            "min_words": MIN_WORDS, "words": words, "tokens_est": round(words * 1.3),
            "top_categories": cats.most_common(20),
            "longest_pages": [{"title": t, "words": w} for w, t in lengths[:10]],
        }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "stats.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    for src, s in result.items():
        print(f"== {src}: {s['pages']} pages gardees / {s['pages_raw']} brutes "
              f"({s['pages_filtered_out']} ecartees < {MIN_WORDS} mots)")
        print(f"   {s['words']} mots, ~{s['tokens_est']} tokens (mots x 1.3)")
        print("   top categories: " + ", ".join(f"{c} ({k})" for c, k in s["top_categories"][:10]))
        print("   plus longues: " + ", ".join(f"{p['title']} ({p['words']})"
                                              for p in s["longest_pages"]))
