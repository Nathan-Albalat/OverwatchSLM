"""Energie par requete d'une config locale (Ollama) : puissance GPU mesuree par nvidia-smi (10 Hz),
CPU estime (hypothese, pas de capteur accessible sous Windows). Resultats ajoutes a eval/report/power.jsonl.

Protocole :
1. tous les modeles Ollama decharges, puissance au repos mesuree pendant IDLE_S secondes ;
2. passages RAG calcules AVANT la mesure (la recherche BM25 + RRF est du CPU leger) ;
3. phase « embeddings » : encodage des questions une par une (qwen3-embedding, sans cache), comme en usage reel ;
4. phase « generation » : le modele repond aux n questions (requete de chauffe non comptee) ;
5. energie = integrale de la puissance sur la phase ; marginale = energie - repos x duree.

Usage : python -m bench.power <config> [--n 235] [--cpu-only]
"""
import argparse
import datetime as dt
import json
import subprocess
import tempfile
import time
from pathlib import Path

import requests

from bench import common as C
from bench.backends import make_backend
from bench.prompts import build_messages
from bench.run import _retrieve

OLLAMA = "http://localhost:11434"
EMBED_MODEL = "qwen3-embedding:0.6b"
IDLE_S = 20
CPU_W_ACTIVE = 35    # hypothese : CPU peu sollicite pendant une inference GPU (charge legere, 1-2 coeurs)
CPU_W_FULL = 120     # hypothese : CPU a pleine charge pour l'inference sur CPU seul (TDP du Ryzen 7 9800X3D)
OUT = C.ROOT / "eval" / "report" / "power.jsonl"


class PowerLog:
    """nvidia-smi en tache de fond, un echantillon toutes les 100 ms."""

    def __enter__(self):
        self.path = Path(tempfile.mkstemp(suffix=".csv")[1])
        self.f = open(self.path, "w")
        self.p = subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,power.draw,utilization.gpu",
                                   "--format=csv,noheader,nounits", "-lms", "100"], stdout=self.f)
        time.sleep(1)
        return self

    def __exit__(self, *a):
        self.p.terminate()
        self.p.wait()
        self.f.close()

    def samples(self):
        out = []
        for line in self.path.read_text().splitlines():
            try:
                ts, w, u = [x.strip() for x in line.split(",")]
                out.append((dt.datetime.strptime(ts, "%Y/%m/%d %H:%M:%S.%f").timestamp(), float(w), float(u)))
            except ValueError:
                continue
        return out


def energy_j(samples, t0, t1):
    """Integrale (trapezes) de la puissance entre t0 et t1, en joules."""
    pts = [(t, w) for t, w, _ in samples if t0 <= t <= t1]
    return sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(pts, pts[1:]))


def mean_w(samples, t0, t1):
    ws = [w for t, w, _ in samples if t0 <= t <= t1]
    return sum(ws) / len(ws) if ws else 0.0


def unload_all():
    for m in requests.get(f"{OLLAMA}/api/ps", timeout=10).json().get("models", []):
        requests.post(f"{OLLAMA}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=60)


def embed_one(text, cpu_only):
    body = {"model": EMBED_MODEL, "input": [text], "keep_alive": "10m"}
    if cpu_only:
        body["options"] = {"num_gpu": 0}
    requests.post(f"{OLLAMA}/api/embed", json=body, timeout=300).raise_for_status()


def run(name, n, cpu_only):
    from rag.embed import query_text
    cfg = dict(C.get_config(name))
    if cpu_only:
        cfg["num_gpu"] = 0
    qs = C.load_test()[:n]
    k = (cfg.get("rag") or {}).get("k")
    print(f"[power] {name}{' (CPU seul)' if cpu_only else ''} : {len(qs)} questions, passages RAG k={k}")
    passages = {q["id"]: (_retrieve(q["question"], k) if k else None) for q in qs}
    backend = make_backend(cfg)
    with PowerLog() as log:
        unload_all()
        time.sleep(5)
        i0 = time.time()
        time.sleep(IDLE_S)
        i1 = time.time()
        e0 = e1 = None
        if k:
            embed_one("warm-up", cpu_only)
            e0 = time.time()
            for q in qs:
                embed_one(query_text(q["question"]), cpu_only)
            e1 = time.time()
        backend.prepare()
        g0 = time.time()
        lat, out_tok = [], 0
        for q in qs:
            res = backend.answer(build_messages(q["question"], passages[q["id"]]))
            lat.append(res["latency_s"])
            out_tok += res["out_tokens"] or 0
        g1 = time.time()
        time.sleep(1)
    s = log.samples()
    idle = mean_w(s, i0, i1)

    def phase(t0, t1):
        e = energy_j(s, t0, t1)
        return {"seconds": round(t1 - t0, 1), "gpu_mean_w": round(mean_w(s, t0, t1), 1),
                "gpu_j": round(e, 1), "gpu_marginal_j": round(e - idle * (t1 - t0), 1)}

    gen = phase(g0, g1)
    emb = phase(e0, e1) if k else None
    cpu_w = CPU_W_FULL if cpu_only else CPU_W_ACTIVE
    t_req = (g1 - g0 + ((e1 - e0) if k else 0)) / len(qs)
    gpu_marg = (gen["gpu_marginal_j"] + (emb["gpu_marginal_j"] if emb else 0)) / len(qs)
    gpu_tot = (gen["gpu_j"] + (emb["gpu_j"] if emb else 0)) / len(qs)
    rec = {"config": name, "cpu_only": cpu_only, "n": len(qs), "ts": dt.datetime.now().isoformat(timespec="seconds"),
           "gpu_idle_w": round(idle, 1), "generation": gen, "embedding": emb,
           "latency_p50_s": round(sorted(lat)[len(lat) // 2], 3), "out_tokens_mean": round(out_tok / len(qs), 1),
           "seconds_per_request": round(t_req, 3),
           "gpu_wh_per_request_marginal": round(gpu_marg / 3600, 5),
           "gpu_wh_per_request_total": round(gpu_tot / 3600, 5),
           "cpu_w_assumed": cpu_w, "cpu_wh_per_request": round(cpu_w * t_req / 3600, 5)}
    rec["wh_per_request"] = round((0 if cpu_only else rec["gpu_wh_per_request_marginal"]) + rec["cpu_wh_per_request"], 5)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, indent=1, ensure_ascii=False))
    unload_all()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--n", type=int, default=235)
    ap.add_argument("--cpu-only", action="store_true")
    a = ap.parse_args()
    run(a.config, a.n, a.cpu_only)


if __name__ == "__main__":
    main()
