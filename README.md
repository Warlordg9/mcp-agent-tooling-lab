# mcp-agent-tooling-lab

[![CI](https://github.com/Warlordg9/mcp-agent-tooling-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Warlordg9/mcp-agent-tooling-lab/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![MCP 2026-07-28](https://img.shields.io/badge/MCP-2026--07--28-6f42c1)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A stateless **Model Context Protocol (MCP 2026-07-28)** server for a course-consultation booking domain, plus a reproducible evaluation of two practical questions for LLM agents:

1. **Tool selection at scale.** How does tool-choice accuracy degrade as the toolset grows from 5 to 100? Does embedding-based retrieval (top-5) beat putting every description into the context?
2. **Agent loops.** When a tool fails silently, which helps more: a `LoopGuard` in the harness, or fixing the tool to return an actionable message?

Everything runs locally on an open model (`qwen2.5:3b` and `bge-m3` via Ollama): no API keys, zero cost, raw logs committed.

> Built as a university homework (Russian materials are in [`docs/`](docs/)). The code is organised as a standalone project so it can keep growing.

## Highlights

- **Spec-compliant stateless MCP server** (`mcp==2.3.0`, `MCPServer`): `server/discover` plus a per-request `_meta` envelope, no `initialize` and no `Mcp-Session-Id`. Legacy handshakes are rejected with `-32022 UNSUPPORTED_PROTOCOL_VERSION`.
- **Tool design for LLMs:** 6 namespaced tools (`consult_*`); every closed set is an `enum`; every field has a `description`; `additionalProperties: false`; each description says when to use the tool and when *not* to; `response_format: concise | detailed` (detailed is 3–6.5× more tokens).
- **Errors as data, not stack traces:** schema violations and domain errors come back as `isError: true` with a "how to fix" hint. The experiment shows the model fixing its own call from that hint.
- **Explicit state handles instead of sessions:** `booking_id`, `student_id`, and opaque pagination `cursor`s. Any request can be served by a fresh server instance.
- **Tested:** 19 pytest tests (protocol, schemas, success and error paths for every tool), an MCP Inspector CLI run, and CI on GitHub Actions.
- **Evaluation harness:** a 100-tool pool (6 own, 25 near-domain distractors, 69 public-MCP-style tools), 30 labelled queries, 720 selection runs, 60 agent episodes, and 95% bootstrap CIs that resample *queries*, not runs.

## Repository layout

```
consult_mcp/          MCP server: data, store (state), schemas, server + middleware
tests/                pytest suite (+ saved run log)
inspector/            MCP Inspector CLI script and log
experiment/
  pool.py             builds the 100-tool pool
  part_a.py           tool selection: N in {5,20,50,100}, all-in-context vs top-5 retrieval
  part_b.py           agent loop on a flaky tool: no guard / LoopGuard / hinted tool
  analysis.ipynb      analysis of raw logs (bootstrap CIs, tables, plot)
  data/ logs/ results/
task1/                context-cost theory (derivation and numbers)
report/               PDF report (LaTeX)
scripts/              token measurement, progress counter
docs/                 assignment and homework write-up (RU), resume notes, roadmap
```

## Quick start

```bash
make install            # uv venv + editable install with dev and experiment extras
make test               # 19 tests
make serve-http         # POST http://127.0.0.1:8765/mcp  (or: make serve for stdio)
make inspector          # MCP Inspector CLI run -> inspector/inspector_log.txt
```

Talk to the server over raw HTTP (MCP 2026-07-28):

```bash
curl -s localhost:8765/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' -H 'Mcp-Method: server/discover' \
  -d '{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{
        "io.modelcontextprotocol/protocolVersion":"2026-07-28",
        "io.modelcontextprotocol/clientInfo":{"name":"curl","version":"1"},
        "io.modelcontextprotocol/clientCapabilities":{}}}}'
```

## Tools

| Tool | Purpose |
|---|---|
| `consult_search_slots` | find slots on a date, filter by format, topic, or teacher, paginate with `cursor` |
| `consult_get_slot` | details of one slot |
| `consult_book` | book a slot for a student and return the `booking_id` handle (idempotent via `idempotency_key`) |
| `consult_get_booking` | verify a booking's status |
| `consult_list_bookings` | a student's bookings |
| `consult_cancel` | cancel the student's own booking |

## Running the experiment

```bash
ollama pull qwen2.5:3b && ollama pull bge-m3
make pool experiment-a experiment-b analysis report
```

Setup: `qwen2.5:3b` (Q4_K_M), `temperature=0.7`, seeds 1–3, `num_ctx=16384` for every N (Ollama's 4096 default would silently truncate N=100), on an Apple M1 with 16 GB. Results, the token table, the loop table, and threats to validity are in the [report](report/report.pdf) and the [notebook](experiment/analysis.ipynb).

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md): a larger model sweep, a query-rewriting retriever, tool-set caching experiments, and a real calendar backend.

## License

MIT
