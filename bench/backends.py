"""Backends : interface commune answer(messages) -> dict(text, latency_s, ttft_s, out_tokens, think_tokens,
tok_s, vram_mb, cost_usd, in_tokens, raw_meta)."""
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BENCH_CWD = ROOT / "data" / "bench_cwd"   # dossier vide : pas de CLAUDE.md projet pour claude -p

LIMIT_RE = re.compile(r"limit|quota|usage|overloaded|too many requests|credit", re.I)


class RateLimitError(RuntimeError):
    """Limite d'abonnement / quota atteint : arret propre, reprise plus tard."""


class BackendError(RuntimeError):
    pass


def _empty():
    return {"text": "", "latency_s": None, "ttft_s": None, "out_tokens": None, "think_tokens": None,
            "tok_s": None, "vram_mb": None, "cost_usd": 0.0, "in_tokens": None, "raw_meta": {}}


class Backend:
    def __init__(self, cfg):
        self.cfg = cfg

    def prepare(self):
        pass

    def answer(self, messages):
        raise NotImplementedError


class OllamaBackend(Backend):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.url = cfg.get("base_url", "http://localhost:11434")

    def _payload(self, messages, max_tokens):
        c = self.cfg
        return {"model": c["model"], "messages": messages, "stream": True, "think": c.get("think", False),
                "keep_alive": c.get("keep_alive", "30m"),
                "options": {"temperature": c.get("temperature", 0), "num_predict": max_tokens,
                            "num_ctx": c.get("num_ctx", 8192)}}   # defaut Ollama trop court pour 5 passages RAG

    def prepare(self):
        # requete de chauffe non comptee : evite de mesurer le chargement du modele
        try:
            r = requests.post(f"{self.url}/api/chat", json=self._payload(
                [{"role": "user", "content": "Hi"}], 1) | {"stream": False}, timeout=600)
            r.raise_for_status()
        except requests.RequestException as e:
            raise BackendError(f"ollama indisponible ou modele absent ({self.cfg['model']}): {e}")

    def _vram_mb(self):
        try:
            for m in requests.get(f"{self.url}/api/ps", timeout=10).json().get("models", []):
                if m.get("name") == self.cfg["model"] or m.get("model") == self.cfg["model"]:
                    return round(m.get("size_vram", 0) / 1e6)
        except requests.RequestException:
            pass
        return None

    def answer(self, messages):
        res = _empty()
        t0 = time.time()
        ttft = None
        parts, final = [], {}
        try:
            with requests.post(f"{self.url}/api/chat",
                               json=self._payload(messages, self.cfg.get("max_tokens", 512)),
                               stream=True, timeout=900) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    d = json.loads(line)
                    msg = d.get("message", {})
                    if ttft is None and (msg.get("content") or msg.get("thinking")):
                        ttft = time.time() - t0
                    parts.append(msg.get("content", ""))
                    if d.get("done"):
                        final = d
        except requests.RequestException as e:
            raise BackendError(f"ollama: {e}")
        res["latency_s"] = time.time() - t0
        res["text"] = "".join(parts).strip()
        res["ttft_s"] = ttft
        res["out_tokens"] = final.get("eval_count")
        res["in_tokens"] = final.get("prompt_eval_count")
        res["think_tokens"] = 0
        if final.get("eval_count") and final.get("eval_duration"):
            res["tok_s"] = final["eval_count"] / (final["eval_duration"] / 1e9)
        res["vram_mb"] = self._vram_mb()
        res["raw_meta"] = {"load_s": (final.get("load_duration") or 0) / 1e9}
        return res


class OpenAIBackend(Backend):
    def answer(self, messages):
        c = self.cfg
        base = c.get("base_url", "http://localhost:8080/v1")
        headers = {"Authorization": f"Bearer {c.get('api_key', 'none')}"}
        body = {"model": c["model"], "messages": messages, "stream": True,
                "stream_options": {"include_usage": True},
                "temperature": c.get("temperature", 0), "max_tokens": c.get("max_tokens", 512)}
        res = _empty()
        t0 = time.time()
        t_first = None
        parts, usage = [], {}
        try:
            with requests.post(f"{base}/chat/completions", json=body, headers=headers, stream=True,
                               timeout=900) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line or not line.startswith(b"data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == b"[DONE]":
                        break
                    d = json.loads(payload)
                    if d.get("usage"):
                        usage = d["usage"]
                    for ch in d.get("choices", []):
                        delta = ch.get("delta", {}).get("content")
                        if delta:
                            if t_first is None:
                                t_first = time.time()
                            parts.append(delta)
        except requests.RequestException as e:
            raise BackendError(f"openai: {e}")
        t_end = time.time()
        res["latency_s"] = t_end - t0
        res["text"] = "".join(parts).strip()
        res["ttft_s"] = (t_first - t0) if t_first else None
        res["out_tokens"] = usage.get("completion_tokens")
        res["in_tokens"] = usage.get("prompt_tokens")
        res["think_tokens"] = 0
        if res["out_tokens"] and t_first and t_end > t_first:
            res["tok_s"] = res["out_tokens"] / (t_end - t_first)
        res["vram_mb"] = c.get("vram_mb")
        return res


class ClaudeCliBackend(Backend):
    """claude -p en mode headless (abonnement, pas d'API payante). Contexte propre : aucun outil, aucun
    CLAUDE.md, cwd vide. tok/s = INDICATIF (reseau inclus, tokens de reflexion inclus ; think_tokens a part).
    cost_usd = cout API equivalent, pas une depense reelle."""

    def prepare(self):
        self.exe = shutil.which("claude")
        if not self.exe:
            raise BackendError("executable `claude` introuvable dans le PATH")
        BENCH_CWD.mkdir(parents=True, exist_ok=True)

    def answer(self, messages):
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        user = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
        cmd = [self.exe, "-p", "--output-format", "json", "--tools", "", "--system-prompt", system,
               "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
               "--model", self.cfg["model"]]
        last = ""
        for attempt in range(3):
            t0 = time.time()
            try:
                p = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                                   cwd=BENCH_CWD, timeout=600)
            except subprocess.TimeoutExpired:
                last = "timeout"
                time.sleep(5 * (attempt + 1))
                continue
            wall = time.time() - t0
            out = (p.stdout or "").strip()
            try:
                d = json.loads(out)
            except ValueError:
                last = f"sortie non JSON (code {p.returncode}): {(out or p.stderr or '')[:300]}"
                if LIMIT_RE.search(out + (p.stderr or "")):
                    raise RateLimitError(last)
                time.sleep(5 * (attempt + 1))
                continue
            if d.get("is_error") or d.get("subtype", "success") != "success":
                last = f"is_error={d.get('is_error')} subtype={d.get('subtype')}: {str(d.get('result'))[:300]}"
                if LIMIT_RE.search(str(d.get("result", "")) + str(d.get("subtype", ""))):
                    raise RateLimitError(last)
                time.sleep(5 * (attempt + 1))
                continue
            res = _empty()
            u = d.get("usage", {}) or {}
            res["text"] = (d.get("result") or "").strip()
            res["latency_s"] = wall
            ttft = d.get("ttft_ms")
            res["ttft_s"] = ttft / 1000 if ttft is not None else None
            res["out_tokens"] = u.get("output_tokens")
            res["think_tokens"] = (u.get("output_tokens_details") or {}).get("thinking_tokens", 0)
            res["in_tokens"] = sum(u.get(k, 0) or 0 for k in
                                   ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            api = d.get("duration_api_ms")
            if res["out_tokens"] and api and ttft is not None and api > ttft:
                res["tok_s"] = res["out_tokens"] / ((api - ttft) / 1000)
            res["cost_usd"] = d.get("total_cost_usd", 0.0)
            res["raw_meta"] = {"duration_ms": d.get("duration_ms"), "duration_api_ms": api}
            return res
        raise BackendError(f"claude -p echoue apres 3 essais: {last}")


class ManualBackend(Backend):
    def answer(self, messages):
        raise BackendError("backend manual : utiliser `ow-bench export-questions <config>` puis `import-answers`")


BACKENDS = {"ollama": OllamaBackend, "openai": OpenAIBackend, "claude_cli": ClaudeCliBackend,
            "manual": ManualBackend}


def make_backend(cfg):
    if cfg["backend"] not in BACKENDS:
        raise BackendError(f"backend inconnu: {cfg['backend']}")
    return BACKENDS[cfg["backend"]](cfg)
