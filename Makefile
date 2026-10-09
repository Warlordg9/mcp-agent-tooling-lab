PY ?= .venv/bin/python
export PYTHONPATH := .

.PHONY: install test lint serve serve-http inspector tokens pool experiment-a experiment-b analysis report progress

install:            ## окружение со всеми зависимостями (нужен arm64-Python на Apple Silicon)
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e ".[dev,experiment]"

test:               ## pytest: протокол, схемы, успех/ошибка каждого инструмента
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check consult_mcp tests

serve:              ## MCP-сервер по stdio
	$(PY) -m consult_mcp.server

serve-http:         ## MCP-сервер по streamable HTTP: POST http://127.0.0.1:8765/mcp
	$(PY) -m consult_mcp.server --http --port 8765

inspector:          ## прогон через MCP Inspector CLI -> inspector/inspector_log.txt
	bash inspector/run_inspector.sh

tokens:             ## размер ответов concise/detailed в токенах
	$(PY) scripts/measure_tokens.py

pool:
	$(PY) experiment/pool.py

experiment-a:       ## часть A: выбор из N (нужна Ollama с qwen2.5:3b и bge-m3)
	$(PY) experiment/part_a.py

experiment-b:       ## часть B: петли и LoopGuard
	$(PY) experiment/part_b.py

analysis:           ## исполнить ноутбук анализа на сырых логах
	$(PY) experiment/build_notebook.py
	cd experiment && ../$(PY) -m jupyter nbconvert --to notebook --execute --inplace analysis.ipynb

report:             ## собрать PDF-отчёт
	cd report && latexmk -xelatex -interaction=nonstopmode report.tex

progress:           ## сколько осталось до полного выполнения ДЗ
	$(PY) scripts/progress.py --detail
