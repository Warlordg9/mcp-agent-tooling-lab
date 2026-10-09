"""Часть B: петли агента на нестабильном инструменте.

consult_search_slots в 50% вызовов (монета с seed по задаче) отвечает:
  * flaky_empty — пустой строкой без объяснения;
  * flaky_hint  — «Ничего не найдено; попробуйте другое значение date.»
Три условия, 20 задач в каждом, один эпизод на задачу:
  no_guard — flaky_empty без LoopGuard;
  guard    — flaky_empty с LoopGuard (3 повтора в окне 6);
  hint     — flaky_hint без LoopGuard;
  stable   — контроль: обычный (стабильный) поиск, без LoopGuard.

LoopGuard (реализация по описанию из лекции): перед исполнением вызова берём
окно из последних 6 попыток вызова (включая текущую); если такая же пара
(имя, аргументы) встречается в окне ≥ 3 раз, вызов не исполняется, модели
возвращается сообщение guard'а. Второе срабатывание завершает эпизод.

Петля в эпизоде (метрика, по последовательности попыток вызова): ≥ 3 одинаковых
вызова подряд или колебание A-B-A-B. Успех: у студента есть активная бронь
у нужного преподавателя по нужной теме в разрешённом окне дат.

Запуск: python experiment/part_b.py  (продолжает с места остановки)
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.client.client import Client  # noqa: E402

from consult_mcp.data import TEACHERS, TOPIC_TITLES  # noqa: E402
from consult_mcp.schemas import TOOL_SPECS  # noqa: E402
from consult_mcp.server import create_server  # noqa: E402
from consult_mcp.store import Store  # noqa: E402
from experiment.common import CHAT_MODEL, DATA, LOGS, NUM_CTX, TEMPERATURE, chat  # noqa: E402

MAX_TURNS = 15
GUARD_REPEATS, GUARD_WINDOW, GUARD_MAX_TRIGGERS = 3, 6, 2
CONDITIONS = {"no_guard": ("flaky_empty", False), "guard": ("flaky_empty", True), "hint": ("flaky_hint", False),
              "stable": ("normal", False)}  # контроль: стабильный инструмент
TOOLS = [{"name": n, "description": s["description"], "parameters": s["input_schema"]} for n, s in TOOL_SPECS.items()]
SYSTEM = ("Ты — агент записи студентов на консультации курса. Действуй только через инструменты consult_*. "
          "Сегодня 2026-10-12. Студент уже дал согласие на любой подходящий слот, переспрашивать не нужно. "
          "Порядок работы: 1) consult_search_slots — найти свободный слот; 2) consult_book — сразу записать студента "
          "на найденный слот (idempotency_key придумай сам); 3) consult_get_booking — проверить, что статус active. "
          "Не отвечай текстом, пока запись не создана. Текстом отвечай только в конце: когда бронь проверена "
          "или когда выполнить задачу невозможно.")
LOG = LOGS / "part_b.jsonl"


def make_tasks(n: int = 20) -> list[dict]:
    """Детерминированные задачи: (студент, преподаватель, тема, желаемая дата, крайняя дата)."""
    store = Store()
    rng = random.Random(7)
    tasks = []
    combos = [(t, topic) for t in TEACHERS for topic in t.topics]
    rng.shuffle(combos)
    i = 0
    while len(tasks) < n:
        t, topic = combos[i % len(combos)]  # равномерно по парам (преподаватель, тема)
        i += 1
        days = sorted({s.date for s in store.slots.values()
                       if s.teacher_id == t.teacher_id and s.free > 0 and topic in s.topics})
        if not days:
            continue
        start = rng.choice(days[:-1] or days)
        deadline = (date.fromisoformat(start) + timedelta(days=6)).isoformat()
        sid = f"st-{1001 + len(tasks):04d}"
        tasks.append({
            "task_id": f"t{len(tasks) + 1:02d}", "student_id": sid, "teacher": t.teacher_id, "topic": topic,
            "date": start, "deadline": deadline,
            "prompt": (f"Я студент {sid}. Запиши меня на консультацию к преподавателю {t.name.split()[0]} "
                       f"({t.teacher_id}) по теме «{TOPIC_TITLES[topic]}» ({topic}). Удобнее всего {start}; "
                       f"если в этот день не выйдет, подойдёт любой день до {deadline} включительно. "
                       f"Подойдёт любой свободный слот. После записи проверь, что бронь активна."),
        })
    return tasks


def signature(name: str, args: dict) -> str:
    return name + json.dumps(args, sort_keys=True, ensure_ascii=False)


def has_loop(seq: list[str]) -> bool:
    for i in range(len(seq) - 2):
        if seq[i] == seq[i + 1] == seq[i + 2]:
            return True
    for i in range(len(seq) - 3):
        if seq[i] == seq[i + 2] and seq[i + 1] == seq[i + 3] and seq[i] != seq[i + 1]:
            return True
    return False


def success(store: Store, task: dict) -> bool:
    for b in store.bookings.values():
        s = store.slots[b.slot_id]
        if (b.student_id == task["student_id"] and b.status == "active" and s.teacher_id == task["teacher"]
                and b.topic == task["topic"] and task["date"] <= s.date <= task["deadline"]):
            return True
    return False


async def run_episode(task: dict, condition: str) -> dict:
    mode, use_guard = CONDITIONS[condition]
    store = Store()
    server = create_server(store, search_mode=mode, rng=random.Random(f"coin-{task['task_id']}"))
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task["prompt"]}]
    attempted: list[str] = []
    trace, prompt_tokens, output_tokens, turns, guard_triggers = [], 0, 0, 0, 0
    end = "max_turns"
    async with Client(server, mode="2026-07-28") as client:
        while turns < MAX_TURNS:
            turns += 1
            resp = chat(messages, TOOLS, seed=int(task["task_id"][1:]))
            prompt_tokens += resp.get("prompt_eval_count") or 0
            output_tokens += resp.get("eval_count") or 0
            msg = resp["message"]
            calls = msg.get("tool_calls") or []
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            if not calls:
                trace.append({"turn": turns, "final_text": msg.get("content")})
                end = "final_answer"
                break
            stop = False
            for call in calls:
                name = call["function"]["name"]
                args = call["function"].get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                sig = signature(name, args)
                attempted.append(sig)
                window = attempted[-GUARD_WINDOW:]
                if use_guard and window.count(sig) >= GUARD_REPEATS:
                    guard_triggers += 1
                    text = (f"LoopGuard: вызов {name} с теми же аргументами повторён {window.count(sig)} раз "
                            f"за последние {GUARD_WINDOW} вызовов и не выполнен. Не повторяй его: измени аргументы "
                            f"(например, другую date) или сообщи пользователю, что сделать не удалось.")
                    is_error, blocked = True, True
                    if guard_triggers >= GUARD_MAX_TRIGGERS:
                        stop = True
                else:
                    r = await client.call_tool(name, args)
                    text = r.content[0].text if r.content else ""
                    is_error, blocked = bool(r.is_error), False
                trace.append({"turn": turns, "tool": name, "args": args, "result": text[:600],
                              "is_error": is_error, "blocked_by_guard": blocked})
                messages.append({"role": "tool", "tool_name": name, "content": text})
                if stop:
                    break
            if stop:
                end = "guard_stop"
                break
    return {"turns": turns, "tool_calls": len(attempted), "executed_calls": sum(not t.get("blocked_by_guard", True)
                                                                              for t in trace if "tool" in t),
            "prompt_tokens": prompt_tokens, "output_tokens": output_tokens,
            "tokens": prompt_tokens + output_tokens, "loop": has_loop(attempted), "guard_triggers": guard_triggers,
            "end": end, "success": success(store, task), "trace": trace}


def main() -> None:
    tasks = make_tasks()
    (DATA / "loop_tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    LOGS.mkdir(parents=True, exist_ok=True)
    done = set()
    if LOG.exists():
        done = {(r["task_id"], r["condition"]) for r in map(json.loads, LOG.read_text(encoding="utf-8").splitlines())}
    with LOG.open("a", encoding="utf-8") as f:
        for condition in CONDITIONS:
            for task in tasks:
                if (task["task_id"], condition) in done:
                    continue
                rec = {"task_id": task["task_id"], "condition": condition, "model": CHAT_MODEL,
                       "num_ctx": NUM_CTX, "temperature": TEMPERATURE, "seed": int(task["task_id"][1:])}
                try:
                    rec |= {"status": "ok", **asyncio.run(run_episode(task, condition))}
                except Exception as exc:  # noqa: BLE001 — упавший эпизод пишется и считается неуспехом
                    rec |= {"status": "failed", "success": False, "loop": None,
                            "error": f"{type(exc).__name__}: {exc}", "trace_py": traceback.format_exc()[-800:]}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                print(condition, task["task_id"], rec.get("status"), "success" if rec["success"] else "fail",
                      "loop" if rec.get("loop") else "", rec.get("turns"), rec.get("tokens"), rec.get("end"), flush=True)


if __name__ == "__main__":
    main()
