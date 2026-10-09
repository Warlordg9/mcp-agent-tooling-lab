"""MCP-сервер записи на консультации курса (спецификация MCP 2026-07-28).

Только stateless-эра: каждый запрос несёт свой `_meta`, версия узнаётся через
`server/discover`; `initialize` отклоняется ошибкой -32022, сессий
(`Mcp-Session-Id`) нет. Состояние домена (брони) адресуется явными
handle-аргументами: `booking_id`, `student_id`, `cursor`.

Запуск:
    python -m consult_mcp.server                      # stdio
    python -m consult_mcp.server --http --port 8765   # streamable HTTP, POST /mcp
"""

from __future__ import annotations

import argparse
import base64
import inspect
import json
import os
import random
from datetime import date
from typing import Any, Literal

from jsonschema import Draft202012Validator
from mcp.server import MCPServer
from mcp.shared.exceptions import MCPError
from mcp_types import UNSUPPORTED_PROTOCOL_VERSION, CallToolResult, TextContent, ToolAnnotations

from .data import FIRST_DAY, LAST_DAY, Slot, teacher_by_id
from .schemas import TOOL_SPECS
from .store import Booking, DomainError, Store

PROTOCOL_VERSION = "2026-07-28"
SearchMode = Literal["normal", "flaky_empty", "flaky_hint"]
FLAKY_HINT = "Ничего не найдено; попробуйте другое значение date."

_VALIDATORS = {name: Draft202012Validator(spec["input_schema"]) for name, spec in TOOL_SPECS.items()}


def error_result(text: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=f"Ошибка: {text}")], is_error=True)


# --- проверка аргументов ----------------------------------------------------

def _describe_error(tool: str, err: Any) -> str:
    props = TOOL_SPECS[tool]["input_schema"]["properties"]
    field = err.path[-1] if err.path else None
    if err.validator == "additionalProperties":
        extra = sorted(set(err.instance) - set(props))
        return (f"неизвестный аргумент {', '.join(map(repr, extra))} у {tool}. "
                f"Как исправить: используйте только {', '.join(props)}.")
    if err.validator == "required":
        missing = err.message.split("'")[1]
        return f"не хватает аргумента {missing!r}. Как исправить: передайте его — {props[missing]['description']}"
    if err.validator == "enum":
        return (f"{field!r} = {err.instance!r} недопустимо. "
                f"Как исправить: выберите одно из значений {', '.join(map(str, err.validator_value))}.")
    if err.validator == "pattern":
        return f"{field!r} = {err.instance!r} в неверном формате. Как исправить: {props[field]['description']}"
    if err.validator in ("minimum", "maximum"):
        spec = props[field]
        return f"{field!r} = {err.instance!r} вне диапазона. Как исправить: число от {spec['minimum']} до {spec['maximum']}."
    if err.validator in ("minLength", "maxLength"):
        return f"{field!r} имеет недопустимую длину. Как исправить: {props[field]['description']}"
    if err.validator == "type":
        return (f"{field!r} должен иметь тип {err.validator_value}, получено {err.instance!r}. "
                f"Как исправить: {props[field]['description'] if field in props else 'передайте объект аргументов'}")
    return f"аргументы не прошли проверку ({err.message}). Как исправить: сверьтесь со схемой {tool}."


def validate_arguments(tool: str, arguments: Any) -> CallToolResult | None:
    if tool not in TOOL_SPECS:
        return error_result(f"инструмента {tool!r} нет. Как исправить: используйте один из {', '.join(TOOL_SPECS)}.")
    errors = sorted(_VALIDATORS[tool].iter_errors(arguments if arguments is not None else {}), key=lambda e: list(e.path))
    if errors:
        return error_result(" ".join(_describe_error(tool, e) for e in errors[:3]))
    return None


async def stateless_guard(ctx: Any, call_next: Any) -> Any:
    """Отклоняет рукопожатие старой эры и проверяет аргументы до вызова инструмента."""
    if ctx.method == "initialize":
        requested = (ctx.params or {}).get("protocolVersion", "")
        raise MCPError(
            UNSUPPORTED_PROTOCOL_VERSION,
            f"Сервер работает только по MCP {PROTOCOL_VERSION}: вызовите server/discover и передавайте _meta в каждом запросе.",
            {"supported": [PROTOCOL_VERSION], "requested": requested},
        )
    if ctx.method == "tools/call":
        params = ctx.params or {}
        rejected = validate_arguments(params.get("name", ""), params.get("arguments"))
        if rejected is not None:
            return rejected
    return await call_next(ctx)


# --- форматирование ответов -------------------------------------------------

def _slot_line(s: Slot) -> str:
    return (f"{s.slot_id} | {s.date} {s.start}–{s.end} | {s.format} | {s.teacher_id} | "
            f"{','.join(s.topics)} | мест {s.free}/{s.capacity}")


def _slot_detail(s: Slot) -> dict[str, Any]:
    t = teacher_by_id(s.teacher_id)
    return {
        "slot_id": s.slot_id, "date": s.date, "start": s.start, "end": s.end, "duration_min": s.duration_min,
        "format": s.format, "location": s.location, "teacher_id": s.teacher_id, "teacher_name": t.name if t else "",
        "topics": list(s.topics), "capacity": s.capacity, "booked": s.booked, "free": s.free, "rules": s.notes,
    }


def _booking_line(b: Booking, s: Slot) -> str:
    return f"{b.booking_id} | {b.slot_id} | {s.date} {s.start}–{s.end} | {s.teacher_id} | {b.topic} | {b.status}"


def _booking_detail(b: Booking, s: Slot) -> dict[str, Any]:
    return {"booking_id": b.booking_id, "student_id": b.student_id, "topic": b.topic, "status": b.status,
            "idempotency_key": b.idempotency_key, "slot": _slot_detail(s)}


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


def _encode_cursor(filters: dict[str, Any], offset: int) -> str:
    raw = json.dumps({"f": filters, "o": offset}, sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, filters: dict[str, Any]) -> int:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        offset = int(data["o"])
    except (ValueError, KeyError, TypeError) as exc:
        raise DomainError("cursor повреждён.",
                          "не передавайте cursor, чтобы получить первую страницу, или возьмите next_cursor из последнего ответа.") from exc
    if data["f"] != filters:
        raise DomainError("cursor относится к поиску с другими фильтрами.",
                          "повторите запрос с теми же date/format/topic/teacher/only_free/limit, что и в запросе, вернувшем cursor, или не передавайте cursor.")
    return offset


# --- сервер -----------------------------------------------------------------

def create_server(store: Store | None = None, search_mode: SearchMode = "normal",
                  rng: random.Random | None = None) -> MCPServer:
    """Собирает сервер. `search_mode` != normal — «нестабильный» поиск для эксперимента с петлями."""
    store = store or Store(os.environ.get("CONSULT_STATE_FILE"))
    rng = rng or random.Random()
    srv = MCPServer(
        "consult-booking", version="1.0.0", title="Запись на консультации курса",
        instructions="Инструменты consult_* ищут слоты консультаций, записывают студента и отменяют его брони. "
                     "Брони адресуются booking_id и student_id; сессий нет.",
        middleware=[stateless_guard],
    )

    def domain(fn):
        def wrapper(**kwargs):
            try:
                return fn(**kwargs)
            except DomainError as exc:
                return error_result(str(exc))
        wrapper.__name__ = fn.__name__
        wrapper.__signature__ = inspect.signature(fn)
        return wrapper

    @domain
    def consult_search_slots(date: str, format: str | None = None, topic: str | None = None,
                             teacher: str | None = None, only_free: bool = True, limit: int = 5,
                             cursor: str | None = None, response_format: str = "concise") -> str | CallToolResult:
        if search_mode != "normal" and rng.random() < 0.5:
            return "" if search_mode == "flaky_empty" else FLAKY_HINT

        filters = {"date": date, "format": format, "topic": topic, "teacher": teacher,
                   "only_free": only_free, "limit": limit}
        offset = _decode_cursor(cursor, filters) if cursor else 0

        def matches(s: Slot) -> bool:
            return ((format is None or s.format == format) and (topic is None or topic in s.topics)
                    and (teacher is None or s.teacher_id == teacher) and (not only_free or s.free > 0))

        found = sorted((s for s in store.slots.values() if s.date == date and matches(s)),
                       key=lambda s: (s.start, s.teacher_id))
        if not found:
            days = sorted({s.date for s in store.slots.values() if matches(s)},
                          key=lambda d: abs((_d(d) - _d(date)).days) if _valid(date) else 0)[:3]
            hint = (f"ближайшие дни с подходящими слотами: {', '.join(sorted(days))}" if days
                    else "ослабьте фильтры (уберите teacher/topic/format)")
            return f"На {date} подходящих слотов нет (расписание есть на {FIRST_DAY}–{LAST_DAY}); {hint}."
        page = found[offset:offset + limit]
        next_cursor = _encode_cursor(filters, offset + limit) if offset + limit < len(found) else None
        if response_format == "detailed":
            return _dump({"date": date, "total": len(found), "offset": offset,
                          "slots": [_slot_detail(s) for s in page], "next_cursor": next_cursor})
        lines = [f"{date}: найдено {len(found)}, показаны {offset + 1}–{offset + len(page)}",
                 *(_slot_line(s) for s in page)]
        if next_cursor:
            lines.append(f"next_cursor: {next_cursor}")
        return "\n".join(lines)

    @domain
    def consult_get_slot(slot_id: str, response_format: str = "concise") -> str | CallToolResult:
        s = store.get_slot(slot_id)
        return _dump(_slot_detail(s)) if response_format == "detailed" else _slot_line(s)

    @domain
    def consult_book(slot_id: str, student_id: str, topic: str, idempotency_key: str,
                     response_format: str = "concise") -> str | CallToolResult:
        b, created = store.book(slot_id, student_id, topic, idempotency_key)
        s = store.slots[b.slot_id]
        if response_format == "detailed":
            return _dump({**_booking_detail(b, s), "created": created})
        note = "" if created else " (повтор по idempotency_key: новая бронь не создана)"
        return f"Записано{note}: {_booking_line(b, s)}"

    @domain
    def consult_get_booking(booking_id: str, student_id: str, response_format: str = "concise") -> str | CallToolResult:
        b = store.get_booking(booking_id, student_id)
        s = store.slots[b.slot_id]
        return _dump(_booking_detail(b, s)) if response_format == "detailed" else _booking_line(b, s)

    @domain
    def consult_list_bookings(student_id: str, status: str = "active",
                              response_format: str = "concise") -> str | CallToolResult:
        items = [b for b in store.bookings.values()
                 if b.student_id == student_id and (status == "all" or b.status == status)]
        items.sort(key=lambda b: (store.slots[b.slot_id].date, store.slots[b.slot_id].start))
        if response_format == "detailed":
            return _dump({"student_id": student_id, "status": status,
                          "bookings": [_booking_detail(b, store.slots[b.slot_id]) for b in items]})
        if not items:
            return f"У {student_id} нет броней со статусом {status}."
        return "\n".join(_booking_line(b, store.slots[b.slot_id]) for b in items)

    @domain
    def consult_cancel(booking_id: str, student_id: str, response_format: str = "concise") -> str | CallToolResult:
        b = store.cancel(booking_id, student_id)
        s = store.slots[b.slot_id]
        if response_format == "detailed":
            return _dump(_booking_detail(b, s))
        return f"Отменено: {_booking_line(b, s)}; место освобождено (свободно {s.free}/{s.capacity})"

    for fn in (consult_search_slots, consult_get_slot, consult_book, consult_get_booking,
               consult_list_bookings, consult_cancel):
        spec = TOOL_SPECS[fn.__name__]
        srv.add_tool(fn, name=fn.__name__, title=spec["title"], description=spec["description"],
                     annotations=ToolAnnotations(**spec["annotations"]), structured_output=False)
        # Публикуем рукописную схему (enum, description, additionalProperties: false).
        srv._tool_manager.get_tool(fn.__name__).parameters = spec["input_schema"]
    srv.store = store  # для тестов и эксперимента
    return srv


def _valid(d: str) -> bool:
    try:
        _d(d)
        return True
    except ValueError:
        return False


def _d(d: str) -> date:
    return date.fromisoformat(d)


def main() -> None:
    parser = argparse.ArgumentParser(description="consult-booking MCP server (MCP 2026-07-28)")
    parser.add_argument("--http", action="store_true", help="streamable HTTP вместо stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    srv = create_server()
    if args.http:
        srv.run("streamable-http", host=args.host, port=args.port, stateless_http=True, json_response=True)
    else:
        srv.run("stdio")


if __name__ == "__main__":
    main()
