"""BM25 maison (index inverse + numpy) : evite toute dependance autre que numpy."""
import math
from collections import Counter

import numpy as np

from rag.common import tokenize


class BM25:
    def __init__(self, texts, k1=1.4, b=0.75):
        self.k1, self.b = k1, b
        post = {}
        lens = np.zeros(len(texts), dtype=np.float32)
        for i, t in enumerate(texts):
            toks = tokenize(t)
            lens[i] = len(toks)
            for term, tf in Counter(toks).items():
                post.setdefault(term, ([], []))
                post[term][0].append(i)
                post[term][1].append(tf)
        self.n = len(texts)
        self.avgdl = float(lens.mean()) if self.n else 1.0
        self.norm = (k1 * (1 - b + b * lens / self.avgdl)).astype(np.float32)
        self.post = {t: (np.asarray(d, dtype=np.int32), np.asarray(f, dtype=np.float32)) for t, (d, f) in post.items()}
        self.idf = {t: math.log(1 + (self.n - len(d) + 0.5) / (len(d) + 0.5)) for t, (d, _) in self.post.items()}

    def scores(self, query):
        s = np.zeros(self.n, dtype=np.float32)
        for term in set(tokenize(query)):
            p = self.post.get(term)
            if p is None:
                continue
            docs, tf = p
            s[docs] += self.idf[term] * tf * (self.k1 + 1) / (tf + self.norm[docs])
        return s

    def top(self, query, n):
        s = self.scores(query)
        if n >= len(s):
            idx = np.argsort(-s)
        else:
            idx = np.argpartition(-s, n)[:n]
            idx = idx[np.argsort(-s[idx])]
        return [(int(i), float(s[i])) for i in idx if s[i] > 0]
