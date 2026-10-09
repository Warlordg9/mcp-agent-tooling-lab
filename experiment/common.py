"""Общие функции эксперимента: вызовы Ollama, эмбеддинги, бутстрэп."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "experiment" / "data"
LOGS = ROOT / "experiment" / "logs"
RESULTS = ROOT / "experiment" / "results"

OLLAMA = "http://127.0.0.1:11434"
CHAT_MODEL = "qwen2.5:3b"
EMBED_MODEL = "bge-m3"
NUM_CTX = 16384  # одинаковый для всех N; дефолт Ollama (4096) молча обрезал бы N=100
TEMPERATURE = 0.7


def _post(path: str, payload: dict, timeout: float = 600) -> dict:
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def to_ollama_tool(tool: dict) -> dict:
    return {"type": "function", "function": {"name": tool["name"], "description": tool["description"],
                                             "parameters": tool["parameters"]}}


def chat(messages: list[dict], tools: list[dict], seed: int, num_predict: int = 300) -> dict:
    """Один запрос к модели; возвращает ответ Ollama плюс wall_s."""
    t0 = time.time()
    resp = _post("/api/chat", {
        "model": CHAT_MODEL, "messages": messages, "tools": [to_ollama_tool(t) for t in tools],
        "stream": False, "keep_alive": "60m",
        "options": {"temperature": TEMPERATURE, "seed": seed, "num_ctx": NUM_CTX, "num_predict": num_predict},
    })
    resp["wall_s"] = round(time.time() - t0, 2)
    return resp


def tokenize_count(text: str) -> int:
    """Число токенов текста токенизатором модели (через /api/embed нельзя, поэтому /api/generate raw)."""
    resp = _post("/api/generate", {"model": CHAT_MODEL, "prompt": text, "raw": True, "stream": False,
                                   "options": {"num_predict": 1, "num_ctx": NUM_CTX}, "keep_alive": "60m"})
    return resp.get("prompt_eval_count", 0)


def embed(texts: list[str]) -> np.ndarray:
    resp = _post("/api/embed", {"model": EMBED_MODEL, "input": texts, "keep_alive": "60m"})
    v = np.array(resp["embeddings"], dtype=float)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def bootstrap_ci(per_query: np.ndarray, n_boot: int = 10_000, seed: int = 0) -> tuple[float, float, float]:
    """95% перцентильный интервал среднего; ресэмплируются запросы (строки), не запуски."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(per_query), size=(n_boot, len(per_query)))
    means = per_query[idx].mean(axis=1)
    return float(per_query.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
