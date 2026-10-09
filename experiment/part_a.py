"""Часть A: точность выбора инструмента из N описаний.

Для каждого запроса q и N ∈ {5, 20, 50, 100}:
  S_N(q) = {gold} ∪ первые N−1 инструментов из перемешанного (seed по q) пула без gold.
  Множества вложены: S_5 ⊂ S_20 ⊂ S_50 ⊂ S_100 = весь пул. Порядок в контексте —
  общий фиксированный порядок пула (одна перестановка с seed 42).
  (A) в контекст идут все N описаний;
  (B) по эмбеддингам bge-m3 отбираются top-5 из S_N, в контекст идут только они.
По 3 запуска (seed 1..3, temperature 0.7) на каждую пару (q, N, вариант).
Каждый запуск пишется в logs/part_a.jsonl; упавшие запуски тоже пишутся и считаются ошибкой.

Запуск: python experiment/part_a.py   (повторный запуск продолжает с места остановки)
"""

from __future__ import annotations

import json
import random
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from experiment.common import CHAT_MODEL, DATA, EMBED_MODEL, LOGS, NUM_CTX, TEMPERATURE, chat, embed  # noqa: E402

NS = (5, 20, 50, 100)
RUNS = (1, 2, 3)
K = 5
SYSTEM = ("Ты — ассистент студента учебного курса. Тебе доступны инструменты. "
          "Выбери ровно один инструмент, который лучше всего выполняет запрос пользователя, "
          "и вызови его с аргументами из запроса. Не отвечай обычным текстом.")
LOG = LOGS / "part_a.jsonl"


def candidate_sets(pool: list[dict], queries: list[dict]) -> dict[tuple[str, int], list[str]]:
    order = [t["name"] for t in pool]
    random.Random(42).shuffle(order)
    rank = {n: i for i, n in enumerate(order)}
    sets = {}
    for q in queries:
        others = [n for n in order if n != q["gold"]]
        random.Random(f"cand-{q['id']}").shuffle(others)
        for n in NS:
            chosen = [q["gold"], *others[: n - 1]]
            sets[(q["id"], n)] = sorted(chosen, key=rank.__getitem__)
    return sets


def selected_tool(message: dict, names: list[str]) -> str | None:
    calls = message.get("tool_calls") or []
    if calls:
        return calls[0]["function"]["name"]
    text = message.get("content") or ""
    hits = [n for n in names if n in text]  # модель иногда пишет вызов текстом
    return max(hits, key=len) if hits else None


def main() -> None:
    pool = json.loads((DATA / "tool_pool.json").read_text(encoding="utf-8"))
    queries = json.loads((DATA / "queries.json").read_text(encoding="utf-8"))
    by_name = {t["name"]: t for t in pool}
    sets = candidate_sets(pool, queries)

    tool_vecs = dict(zip(by_name, embed([f"{t['name']}: {t['description']}" for t in pool])))
    query_vecs = dict(zip((q["id"] for q in queries), embed([q["query"] for q in queries])))

    LOGS.mkdir(parents=True, exist_ok=True)
    done = set()
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["query_id"], r["N"], r["variant"], r["run"]))

    total = len(queries) * len(NS) * 2 * len(RUNS)
    with LOG.open("a", encoding="utf-8") as f:
        for n in NS:
            for variant in ("A", "B"):
                for q in queries:
                    cand = sets[(q["id"], n)]
                    retrieved = None
                    if variant == "B":
                        sims = {c: float(tool_vecs[c] @ query_vecs[q["id"]]) for c in cand}
                        retrieved = sorted(cand, key=lambda c: -sims[c])[:K]
                    shown = cand if variant == "A" else retrieved
                    for run in RUNS:
                        key = (q["id"], n, variant, run)
                        if key in done:
                            continue
                        rec = {"query_id": q["id"], "gold": q["gold"], "N": n, "variant": variant, "run": run,
                               "model": CHAT_MODEL, "embed_model": EMBED_MODEL, "num_ctx": NUM_CTX,
                               "temperature": TEMPERATURE, "seed": run, "shown_tools": shown,
                               "retrieved_top5": retrieved,
                               "recall_hit": (q["gold"] in retrieved) if retrieved is not None else None}
                        try:
                            resp = chat([{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": q["query"]}],
                                        [by_name[s] for s in shown], seed=run)
                            msg = resp["message"]
                            sel = selected_tool(msg, shown)
                            rec |= {"status": "ok", "selected": sel, "correct": sel == q["gold"],
                                    "prompt_eval_count": resp.get("prompt_eval_count"),
                                    "eval_count": resp.get("eval_count"), "wall_s": resp["wall_s"],
                                    "response": {"content": msg.get("content"), "tool_calls": msg.get("tool_calls")}}
                        except Exception as exc:  # noqa: BLE001 — неудачный запуск пишется и считается ошибкой
                            rec |= {"status": "failed", "selected": None, "correct": False,
                                    "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-500:]}
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f.flush()
                        done.add(key)
                        print(f"[{len(done)}/{total}] N={n} {variant} {q['id']} r{run}: "
                              f"{rec['selected']} {'OK' if rec['correct'] else 'x'} {rec.get('wall_s')}", flush=True)


if __name__ == "__main__":
    main()
