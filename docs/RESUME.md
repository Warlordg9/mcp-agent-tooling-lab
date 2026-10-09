# Строка для резюме / Resume entry

Ссылка: https://github.com/Warlordg9/mcp-agent-tooling-lab

## English

**MCP Agent Tooling Lab** — Python, MCP, Ollama, pytest, GitHub Actions
- Built a spec-compliant stateless MCP (2026-07-28) server with 6 namespaced tools: strict JSON schemas, actionable `isError` hints instead of stack traces, explicit state handles instead of sessions; 19 tests plus MCP Inspector checks in CI.
- Designed and ran a reproducible evaluation of LLM tool selection over 5–100 tools (720 runs, bootstrap CIs over queries), comparing full-context selection with top-5 embedding retrieval, and an agent-loop study of a harness LoopGuard vs. an improved tool response.

One-liner: *Stateless MCP server and an evaluation harness for LLM tool selection at scale and agent loop guards (Python, Ollama, bootstrap statistics).*

## Русский

**MCP Agent Tooling Lab** — Python, MCP, Ollama, pytest, GitHub Actions
- Разработал stateless MCP-сервер по спецификации 2026-07-28 с 6 инструментами в общем пространстве имён: строгие JSON-схемы, ошибки с подсказками вместо стектрейсов, состояние через явные handle-аргументы; 19 тестов и проверка MCP Inspector, CI на GitHub Actions.
- Спроектировал и провёл воспроизводимый эксперимент по выбору инструмента LLM-агентом из 5–100 вариантов (720 запусков, бутстрэп-интервалы по запросам): сравнение полного контекста и top-5 поиска по эмбеддингам; исследование петель агента — LoopGuard в harness против исправленного ответа инструмента.

<!-- После завершения эксперимента сюда добавляются ключевые цифры (точность при N=100 для A и B, сокращение токенов, эффект на петли). -->
