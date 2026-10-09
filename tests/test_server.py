"""Тесты сервера consult_mcp: протокол 2026-07-28, схемы, успех и ошибка для каждого инструмента."""

from __future__ import annotations

import random

import pytest
from mcp.client.client import Client
from mcp.shared.exceptions import MCPError
from starlette.testclient import TestClient

from consult_mcp.schemas import TOOL_SPECS
from consult_mcp.server import FLAKY_HINT, create_server
from consult_mcp.store import Store

pytestmark = pytest.mark.anyio

STUDENT = "st-1001"
META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def server():
    return create_server(Store())


async def call(server, name, args):
    async with Client(server, mode="2026-07-28") as c:
        r = await c.call_tool(name, args)
        return r.is_error, (r.content[0].text if r.content else "")


async def book(server, slot="s-1014-iva-1000", key="key-000001", topic="homework"):
    return await call(server, "consult_book",
                      {"slot_id": slot, "student_id": STUDENT, "topic": topic, "idempotency_key": key})


def booking_id(text: str) -> str:
    return next(tok for tok in text.replace("|", " ").split() if tok.startswith("b-"))


# --- протокол ------------------------------------------------------------------

def http_post(client, method, params=None, *, headers=None, envelope=True):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": dict(params or {})}
    hdr = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if envelope:
        body["params"]["_meta"] = META
        hdr |= {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": method}
    return client.post("/mcp", json=body, headers=hdr | (headers or {}))


def test_http_discover_and_stateless():
    app = create_server(Store()).streamable_http_app(stateless_http=True, json_response=True)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        r = http_post(client, "server/discover")
        assert r.status_code == 200 and "result" in r.json()
        assert "mcp-session-id" not in {k.lower() for k in r.headers}
        r = http_post(client, "tools/list")
        names = [t["name"] for t in r.json()["result"]["tools"]]
        assert names == list(TOOL_SPECS)
        r = http_post(client, "tools/call", {"name": "consult_get_slot", "arguments": {"slot_id": "s-1014-iva-1000"}},
                      headers={"Mcp-Name": "consult_get_slot"})
        assert r.json()["result"]["isError"] is False


def test_http_initialize_rejected():
    app = create_server(Store()).streamable_http_app(stateless_http=True, json_response=True)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        r = http_post(client, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                             "clientInfo": {"name": "old", "version": "1"}}, envelope=False)
        assert r.json()["error"]["code"] == -32022
        assert "mcp-session-id" not in {k.lower() for k in r.headers}


def _leaf_errors(exc: BaseException):
    if isinstance(exc, BaseExceptionGroup):
        for inner in exc.exceptions:
            yield from _leaf_errors(inner)
    else:
        yield exc


async def test_legacy_client_rejected(server):
    with pytest.raises(BaseException) as info:  # noqa: B017 — проверяем код ошибки ниже
        async with Client(server, mode="legacy") as c:
            await c.list_tools()
    codes = [e.code for e in _leaf_errors(info.value) if isinstance(e, MCPError)]
    assert -32022 in codes


# --- дизайн схем ---------------------------------------------------------------

async def test_schemas_published(server):
    async with Client(server, mode="2026-07-28") as c:
        tools = (await c.list_tools()).tools
    assert len(tools) >= 4 and all(t.name.startswith("consult_") for t in tools)
    for t in tools:
        schema = t.input_schema
        assert schema["additionalProperties"] is False
        for name, prop in schema["properties"].items():
            assert prop.get("description"), (t.name, name)
        assert "response_format" in schema["properties"]
        assert schema["properties"]["response_format"]["enum"] == ["concise", "detailed"]
        assert "Не используй" in t.description


async def test_unknown_argument_rejected_with_hint(server):
    is_error, text = await call(server, "consult_get_slot", {"slot_id": "s-1014-iva-1000", "verbose": True})
    assert is_error and "неизвестный аргумент 'verbose'" in text and "Как исправить" in text
    assert "Traceback" not in text and "pydantic" not in text


async def test_unknown_tool(server):
    is_error, text = await call(server, "consult_delete_everything", {})
    assert is_error and "consult_search_slots" in text


# --- consult_search_slots --------------------------------------------------------

async def test_search_success_and_pagination(server):
    is_error, text = await call(server, "consult_search_slots", {"date": "2026-10-15", "only_free": False, "limit": 2})
    assert not is_error and "next_cursor:" in text
    cursor = text.rsplit("next_cursor: ", 1)[1].strip()
    is_error, page2 = await call(server, "consult_search_slots",
                                 {"date": "2026-10-15", "only_free": False, "limit": 2, "cursor": cursor})
    assert not is_error and "показаны 3–4" in page2


async def test_search_errors(server):
    is_error, text = await call(server, "consult_search_slots", {"date": "15.10.2026", "format": "zoom"})
    assert is_error and "YYYY-MM-DD" in text and "online, offline" in text
    is_error, text = await call(server, "consult_search_slots", {"date": "2026-10-15", "cursor": "garbage"})
    assert is_error and "cursor" in text


async def test_search_empty_day_gives_hint(server):
    is_error, text = await call(server, "consult_search_slots", {"date": "2026-10-17"})
    assert not is_error and "ближайшие дни" in text


async def test_concise_shorter_than_detailed(server):
    _, concise = await call(server, "consult_search_slots", {"date": "2026-10-14"})
    _, detailed = await call(server, "consult_search_slots", {"date": "2026-10-14", "response_format": "detailed"})
    assert len(detailed) > 2 * len(concise)


# --- consult_get_slot ----------------------------------------------------------

async def test_get_slot(server):
    is_error, text = await call(server, "consult_get_slot", {"slot_id": "s-1014-iva-1000", "response_format": "detailed"})
    assert not is_error and "Иванова" in text
    is_error, text = await call(server, "consult_get_slot", {"slot_id": "s-0101-abc-0900"})
    assert is_error and "не найден" in text


# --- consult_book --------------------------------------------------------------

async def test_book_success_and_idempotency(server):
    is_error, text = await book(server)
    assert not is_error and "active" in text
    is_error, again = await book(server)
    assert not is_error and "повтор" in again and booking_id(again) == booking_id(text)


async def test_book_errors(server):
    is_error, text = await book(server, topic="project")
    assert is_error and "Тема 'project'" in text
    full = next(s for s in server.store.slots.values() if s.free == 0)
    is_error, text = await book(server, slot=full.slot_id, topic=full.topics[0], key="key-full-01")
    assert is_error and "нет свободных мест" in text


async def test_book_overlap_rejected(server):
    a = server.store.slots["s-1014-iva-1000"]
    a.booked = 0
    await book(server, slot=a.slot_id, key="key-overlap-1")
    is_error, text = await book(server, slot=a.slot_id, key="key-overlap-2")
    assert is_error and "уже записан" in text


# --- consult_get_booking / consult_list_bookings / consult_cancel -------------------

async def test_get_booking(server):
    _, text = await book(server)
    bid = booking_id(text)
    is_error, got = await call(server, "consult_get_booking", {"booking_id": bid, "student_id": STUDENT})
    assert not is_error and "active" in got
    is_error, got = await call(server, "consult_get_booking", {"booking_id": bid, "student_id": "st-9999"})
    assert is_error and "другому студенту" in got


async def test_list_bookings(server):
    is_error, text = await call(server, "consult_list_bookings", {"student_id": STUDENT})
    assert not is_error and "нет броней" in text
    await book(server)
    is_error, text = await call(server, "consult_list_bookings", {"student_id": STUDENT, "status": "all"})
    assert not is_error and "b-" in text
    is_error, text = await call(server, "consult_list_bookings", {"student_id": STUDENT, "status": "pending"})
    assert is_error and "active, cancelled, all" in text


async def test_cancel(server):
    _, text = await book(server)
    bid = booking_id(text)
    is_error, out = await call(server, "consult_cancel", {"booking_id": bid, "student_id": STUDENT})
    assert not is_error and "cancelled" in out
    is_error, out = await call(server, "consult_cancel", {"booking_id": bid, "student_id": STUDENT})
    assert is_error and "уже отменена" in out


async def test_state_survives_new_server_instance(tmp_path):
    """Нет сессий: второй экземпляр сервера с тем же файлом видит бронь по handle."""
    state = tmp_path / "state.json"
    _, text = await book(create_server(Store(state)))
    is_error, got = await call(create_server(Store(state)), "consult_get_booking",
                               {"booking_id": booking_id(text), "student_id": STUDENT})
    assert not is_error and "active" in got


# --- нестабильные режимы для эксперимента с петлями ----------------------------------

async def test_flaky_modes():
    outs = set()
    srv = create_server(Store(), search_mode="flaky_empty", rng=random.Random(0))
    for _ in range(20):
        outs.add((await call(srv, "consult_search_slots", {"date": "2026-10-14"}))[1] == "")
    assert outs == {True, False}
    srv = create_server(Store(), search_mode="flaky_hint", rng=random.Random(0))
    texts = {(await call(srv, "consult_search_slots", {"date": "2026-10-14"}))[1] for _ in range(20)}
    assert FLAKY_HINT in texts
