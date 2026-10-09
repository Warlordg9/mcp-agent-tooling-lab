"""Размер ответа инструментов в токенах для response_format=concise и detailed (3 примера).

Токенизаторы: cl100k_base (tiktoken) и токенизатор qwen2.5:3b (через Ollama, если запущена).
Запуск: python scripts/measure_tokens.py  ->  печатает markdown-таблицу и пишет results/response_tokens.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tiktoken  # noqa: E402
from mcp.client.client import Client  # noqa: E402

from consult_mcp.server import create_server  # noqa: E402
from consult_mcp.store import Store  # noqa: E402

EXAMPLES = [
    ("consult_search_slots", {"date": "2026-10-15", "only_free": False, "limit": 5}, "поиск: 5 слотов за 2026-10-15"),
    ("consult_get_slot", {"slot_id": "s-1014-iva-1000"}, "карточка одного слота"),
    ("consult_list_bookings", {"student_id": "st-1001", "status": "all"}, "брони студента (2 шт.)"),
]


def qwen_tokens(text: str) -> int | None:
    try:
        from experiment.common import tokenize_count
        return tokenize_count(text)
    except Exception:  # noqa: BLE001 — Ollama может быть не запущена
        return None


async def main() -> None:
    enc = tiktoken.get_encoding("cl100k_base")
    srv = create_server(Store())
    rows = []
    async with Client(srv, mode="2026-07-28") as c:
        for i, slot in enumerate(("s-1014-iva-1030", "s-1015-sid-1800")):
            await c.call_tool("consult_book", {"slot_id": slot, "student_id": "st-1001",
                                               "topic": "homework", "idempotency_key": f"measure-{i:04d}"})
        for name, args, label in EXAMPLES:
            row = {"tool": name, "example": label}
            for fmt in ("concise", "detailed"):
                text = (await c.call_tool(name, {**args, "response_format": fmt})).content[0].text
                row[fmt] = {"cl100k": len(enc.encode(text)), "qwen2.5": qwen_tokens(text), "chars": len(text)}
            rows.append(row)
    out = ROOT / "experiment" / "results" / "response_tokens.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("| Пример | concise, cl100k | detailed, cl100k | concise, qwen2.5 | detailed, qwen2.5 | detailed / concise |")
    print("|---|---:|---:|---:|---:|---:|")
    for r in rows:
        c, d = r["concise"], r["detailed"]
        print(f"| `{r['tool']}` — {r['example']} | {c['cl100k']} | {d['cl100k']} | {c['qwen2.5']} | {d['qwen2.5']} "
              f"| ×{d['cl100k'] / c['cl100k']:.1f} |")


if __name__ == "__main__":
    asyncio.run(main())
