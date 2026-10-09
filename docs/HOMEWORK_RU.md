# Домашнее задание: экономика контекста, MCP-сервер, выбор из N и петли

> Подробное описание сдачи на русском. Обзор проекта на английском — в [README](../README.md), условие — в [ASSIGNMENT_RU.md](ASSIGNMENT_RU.md).

Домен — учебная запись на консультации курса (данные вымышленные), тот же, что у навыка `consult-booking` из ДЗ 2В: преподаватели, слоты, брони студентов.

| Задача | Где |
|---|---|
| 1. Теория: экономика контекста | [`task1/theory.md`](../task1/theory.md), проверка чисел [`task1/calc.py`](../task1/calc.py) → [`task1/calc_output.txt`](../task1/calc_output.txt) |
| 2. MCP-сервер (MCP 2026-07-28) | [`consult_mcp/`](../consult_mcp/), тесты [`tests/`](../tests/), лог pytest [`tests/pytest_log.txt`](../tests/pytest_log.txt), прогон MCP Inspector [`inspector/`](../inspector/) |
| 3. Эксперимент | код [`experiment/`](../experiment/), ноутбук [`experiment/analysis.ipynb`](../experiment/analysis.ipynb), сырые логи [`experiment/logs/`](../experiment/logs/), таблицы и график [`experiment/results/`](../experiment/results/) |
| Отчёт (PDF, до 3 страниц) | [`report/report.pdf`](../report/report.pdf), исходник [`report/report.tex`](../report/report.tex) |

Ключи API не нужны и в репозитории не хранятся: эксперимент шёл на локальной открытой модели через Ollama.

## Установка

```bash
uv venv --python 3.12 .venv            # на Apple Silicon нужен arm64-Python
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest -q          # 19 тестов
```

## Задача 2. Сервер `consult_mcp`

Python SDK `mcp==2.3.0`, `from mcp.server import MCPServer`, спецификация **MCP 2026-07-28**:

* **stateless:** нет `initialize` и `Mcp-Session-Id`. Клиент получает версию и возможности через `server/discover`, каждый запрос несёт свой `_meta` (`io.modelcontextprotocol/protocolVersion`, `clientInfo`, `clientCapabilities`). HTTP-режим — `stateless_http=True`, один POST — один JSON-ответ.
* **рукопожатие старой эры отклоняется:** middleware `stateless_guard` отвечает на `initialize` ошибкой `-32022 UNSUPPORTED_PROTOCOL_VERSION` с `data.supported = ["2026-07-28"]`. Это проверяется тестами и Inspector (`--protocol-era legacy` получает отказ).

```bash
PYTHONPATH=. .venv/bin/python -m consult_mcp.server                      # stdio
PYTHONPATH=. .venv/bin/python -m consult_mcp.server --http --port 8765   # POST http://127.0.0.1:8765/mcp
```

### Инструменты (общий префикс `consult_`)

| Инструмент | Что делает | Аннотации |
|---|---|---|
| `consult_search_slots` | слоты на день с фильтрами `format`, `topic`, `teacher`, пагинация `cursor` | read-only |
| `consult_get_slot` | карточка слота по `slot_id` | read-only |
| `consult_book` | запись студента, возвращает handle `booking_id`, статус `active`; идемпотентна по `idempotency_key` | idempotent |
| `consult_get_booking` | статус брони по `booking_id` + `student_id` (проверка результата) | read-only |
| `consult_list_bookings` | брони студента, фильтр `status` | read-only |
| `consult_cancel` | отмена своей брони | destructive |

Дизайн схем ([`consult_mcp/schemas.py`](../consult_mcp/schemas.py)):

* закрытые множества — через `enum`: `format`, `topic`, `teacher`, `status`, `response_format`;
* у каждого поля есть `description`, у каждой схемы — `additionalProperties: false`. SDK по умолчанию генерирует схему без этого и молча принимает лишние аргументы, поэтому сервер публикует рукописные схемы и проверяет аргументы по ним (jsonschema, Draft 2020-12) до вызова инструмента;
* в каждом описании есть «Используй, когда…» и «Не используй для…» со ссылкой на правильный соседний инструмент;
* `response_format: "concise" | "detailed"` есть у всех шести инструментов, по умолчанию `concise`.

**Ошибки** возвращаются как результат с `isError: true`, без стектрейса, в виде «Ошибка: <что не так>. Как исправить: <что сделать>». Примеры из [лога Inspector](../inspector/inspector_log.txt):

* `'date' = '14.10.2026' в неверном формате. Как исправить: День консультации в формате YYYY-MM-DD, например 2026-10-14…`
* `Тема 'project' не принимается в слоте s-1014-iva-1030. Как исправить: выберите одну из тем слота: homework, lecture, или найдите слот с этой темой через consult_search_slots(topic='project').`
* `Бронь 'b-5247a4ad' принадлежит другому студенту. Как исправить: работать можно только со своими бронями…`

**Состояние — только через явные handle-аргументы.** Сессий нет. Бронь адресуется `booking_id`, а чужие брони недоступны: сервер сверяет `student_id`. Продолжение поиска — `cursor` (непрозрачный handle с фильтрами и смещением; cursor от другого запроса отклоняется с подсказкой). Состояние лежит в `Store` и при `CONSULT_STATE_FILE=…` сохраняется в файл, поэтому любой запрос можно выполнить на новом экземпляре сервера (тест `test_state_survives_new_server_instance`).

### Размер ответа: concise и detailed

Получено скриптом [`scripts/measure_tokens.py`](../scripts/measure_tokens.py), числа сохранены в [`experiment/results/response_tokens.json`](../experiment/results/response_tokens.json). Токенизаторы: `cl100k_base` (tiktoken) и токенизатор `qwen2.5:3b` — модели, на которой шёл эксперимент.

| Пример | concise, cl100k | detailed, cl100k | concise, qwen2.5 | detailed, qwen2.5 | detailed / concise |
|---|---:|---:|---:|---:|---:|
| `consult_search_slots` — 5 слотов за 2026-10-15 | 331 | 1048 | 391 | 1067 | ×3,2 |
| `consult_get_slot` — карточка одного слота | 41 | 171 | 52 | 169 | ×4,2 |
| `consult_list_bookings` — 2 брони студента | 80 | 523 | 106 | 534 | ×6,5 |

### Тесты

[`tests/test_server.py`](../tests/test_server.py) — 19 тестов, лог — [`tests/pytest_log.txt`](../tests/pytest_log.txt):

* **протокол:** `server/discover` и `tools/list` по HTTP с `_meta`; в ответах нет `Mcp-Session-Id`; `initialize` получает `-32022`; клиент в режиме `legacy` не подключается;
* **дизайн:** префикс, `additionalProperties: false`, `description` у всех полей, enum у `response_format`, «Не используй» в описаниях; лишний аргумент и неизвестный инструмент дают `isError` с подсказкой;
* **для каждого инструмента — успех и ошибка:** поиск (+ пагинация, пустой день с подсказкой, concise короче detailed), карточка слота, запись (+ идемпотентность, нет мест, неверная тема, повторная запись), статус брони (+ чужая бронь), список броней (+ неверный enum), отмена (+ повторная отмена);
* **состояние:** бронь видна новому экземпляру сервера по handle; нестабильные режимы поиска для задачи 3.

### MCP Inspector

```bash
bash inspector/run_inspector.sh      # npx @modelcontextprotocol/inspector@2.10.1 --cli … --protocol-era modern
```

Лог — [`inspector/inspector_log.txt`](../inspector/inspector_log.txt): `tools/list --strict` без замечаний к схемам, по успешному и ошибочному вызову для каждого из 6 инструментов (ошибки — `isError: true`, CLI выходит с кодом 5 `tool_is_error`), и отказ подключению старой эры (`--protocol-era legacy`).

## Задача 3. Эксперимент

Протокол, результаты и угрозы валидности — в [отчёте](../report/report.pdf) и [ноутбуке](../experiment/analysis.ipynb). Коротко:

* **модель:** `qwen2.5:3b` (Q4_K_M) через Ollama 0.40.2 на Apple M1 16 ГБ; `temperature=0.7`, `seed=1..3`, `num_ctx=16384` (одинаковый для всех N; стандартные 4096 обрезали бы N=100). Эмбеддинги — `bge-m3` через Ollama. Бюджет: \$0, локальный запуск;
* **пул:** [`experiment/data/tool_pool.json`](../experiment/data/tool_pool.json) — 100 инструментов: 6 своих, 25 сгенерированных близких по смыслу (учебное расписание, календари, аудитории, поликлиника), 69 описаний из публичных MCP-серверов; сборка — [`experiment/pool.py`](../experiment/pool.py);
* **запросы:** [`experiment/data/queries.json`](../experiment/data/queries.json) — 30 штук с разметкой: 24 к своим инструментам и 6 «почти похожих», где правильный ответ — отвлекающий инструмент;
* **часть A:** [`experiment/part_a.py`](../experiment/part_a.py) → [`logs/part_a.jsonl`](../experiment/logs/part_a.jsonl) (720 запусков: 30 × 4 N × 2 варианта × 3);
* **часть B:** [`experiment/part_b.py`](../experiment/part_b.py) → [`logs/part_b.jsonl`](../experiment/logs/part_b.jsonl) (20 задач × 3 требуемых условия + контроль со стабильным инструментом = 80 эпизодов, полный trace каждого); задачи — [`experiment/data/loop_tasks.json`](../experiment/data/loop_tasks.json).

Повторить:

```bash
~/.local/ollama/ollama serve &                     # или установленная Ollama
ollama pull qwen2.5:3b && ollama pull bge-m3
.venv/bin/python experiment/pool.py
.venv/bin/python experiment/part_a.py              # продолжает с места остановки
.venv/bin/python experiment/part_b.py
.venv/bin/python experiment/build_notebook.py
cd experiment && ../.venv/bin/jupyter nbconvert --to notebook --execute --inplace analysis.ipynb
```
