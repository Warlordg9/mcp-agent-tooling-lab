"""Сколько осталось до полного выполнения ДЗ: взвешенный прогресс по этапам.

Запуск: python scripts/progress.py          — одна строка
        python scripts/progress.py --detail — разбивка по этапам
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lines(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8")) if path.exists() else 0


def notebook_executed() -> float:
    nb = ROOT / "experiment" / "analysis.ipynb"
    if not nb.exists():
        return 0.0
    cells = [c for c in json.loads(nb.read_text(encoding="utf-8"))["cells"] if c["cell_type"] == "code"]
    ok = [c for c in cells if c.get("outputs") and not any(o["output_type"] == "error" for o in c["outputs"])]
    return len(ok) / len(cells) if cells else 0.0


def repo_published() -> float:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain=v2", "--branch"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:  # noqa: BLE001
        return 0.0
    if "# branch.upstream" not in out:
        return 0.5 if (ROOT / ".git").exists() else 0.0
    return 1.0 if "# branch.ab +0 -0" in out else 0.75


STAGES = [  # (название, вес, функция -> доля 0..1)
    ("Задача 1: теория", 10, lambda: float((ROOT / "task1" / "theory.md").exists())),
    ("Задача 2: сервер, тесты, Inspector", 20, lambda: float((ROOT / "tests" / "pytest_log.txt").exists()
                                                            and (ROOT / "inspector" / "inspector_log.txt").exists())),
    ("Задача 3A: 720 запусков выбора", 30, lambda: min(lines(ROOT / "experiment/logs/part_a.jsonl") / 720, 1)),
    ("Задача 3B: 80 эпизодов петель", 15, lambda: min(lines(ROOT / "experiment/logs/part_b.jsonl") / 80, 1)),
    ("Анализ: ноутбук исполнен", 5, notebook_executed),
    ("Отчёт: report.pdf", 10, lambda: float((ROOT / "report" / "report.pdf").exists())),
    ("Репозиторий на GitHub", 10, repo_published),
]


def main() -> None:
    parts = [(name, w, f()) for name, w, f in STAGES]
    total = sum(w * v for _, w, v in parts) / sum(w for _, w, _ in parts) * 100
    bar = "█" * int(total // 5) + "░" * (20 - int(total // 5))
    a, b = lines(ROOT / "experiment/logs/part_a.jsonl"), lines(ROOT / "experiment/logs/part_b.jsonl")
    print(f"[{bar}] {total:5.1f}% готово, осталось {100 - total:4.1f}%  (A {a}/720, B {b}/80)", flush=True)
    if "--detail" in sys.argv:
        for name, w, v in parts:
            print(f"  {v * 100:5.1f}%  вес {w:2d}  {name}")


if __name__ == "__main__":
    main()
