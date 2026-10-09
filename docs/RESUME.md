# Строка для резюме / Resume entry

Ссылка: https://github.com/Warlordg9/mcp-agent-tooling-lab

## English

**MCP Agent Tooling Lab** — Python, MCP, Ollama, pytest, GitHub Actions
- Built a spec-compliant stateless MCP (2026-07-28) server with 6 namespaced tools: strict JSON schemas, actionable `isError` hints instead of stack traces, explicit state handles instead of sessions; 19 tests in CI plus an MCP Inspector run.
- Ran a reproducible evaluation of LLM tool selection over 5–100 tools (720 runs, bootstrap CIs over queries): top-5 embedding retrieval cut input tokens by up to 7.4×, but at 100 tools it trailed full-context selection by ~8 pp (76% vs 84%), bounded by Recall@5 = 0.83.
- Studied agent failures on a flaky tool (80 episodes): silent errors cost 5–15 pp of success and 25% more tokens, mostly through hallucinated IDs rather than loops; showed that tool error messages must be truthful and that LoopGuard is a safety net, not a fix.

One-liner: *Stateless MCP server and an evaluation harness for LLM tool selection at scale and agent loop guards (Python, Ollama, bootstrap statistics).*

## Русский

**MCP Agent Tooling Lab** — Python, MCP, Ollama, pytest, GitHub Actions
- Разработал stateless MCP-сервер по спецификации 2026-07-28 с 6 инструментами в общем пространстве имён: строгие JSON-схемы, ошибки с подсказками вместо стектрейсов, состояние через явные handle-аргументы; 19 тестов и проверка MCP Inspector, CI на GitHub Actions.
- Провёл воспроизводимый эксперимент по выбору инструмента LLM-агентом из 5–100 вариантов (720 запусков, бутстрэп-интервалы по запросам): поиск top-5 по эмбеддингам сокращает входные токены до 7,4 раза, но при 100 инструментах проигрывает полному контексту ~8 п.п. (76 % против 84 %) из-за Recall@5 = 0,83.
- Исследовал отказы агента на нестабильном инструменте (80 эпизодов): тихий сбой снижает успех на 5–15 п.п. и даёт +25 % токенов, причём через выдумывание идентификаторов, а не петли; показал, что подсказка в ответе инструмента должна быть правдивой, а LoopGuard — лишь страховка.

