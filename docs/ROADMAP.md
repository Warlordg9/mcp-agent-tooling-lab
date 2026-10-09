# Roadmap

Ideas for developing the project after the homework.

## Evaluation
- [ ] Model sweep: qwen2.5 7B/14B, llama3.x, plus one API model (Claude Haiku) under the same protocol, to see whether the A-vs-B crossover moves with model size.
- [ ] Larger query set (≥ 100) with an inter-annotator check of the gold labels.
- [ ] Retrieval variants: BM25, hybrid BM25 + embeddings, and a query rewritten by the LLM before search (the realistic "search tool" agent loop).
- [ ] Measure the real cost with prefix caching: a static tool list (cacheable) vs dynamic top-k (not cacheable), against the theory in `task1/`.
- [ ] Part B with several seeds per task and more failure types (timeouts, partial results, wrong-type errors).

## Server
- [ ] Real backend (CalDAV / Google Calendar) behind the same `consult_*` interface.
- [ ] Resources (`consult://slots/{date}`) and prompts alongside tools.
- [ ] Auth: map `student_id` to an OAuth subject instead of trusting the argument.
- [ ] Publish to PyPI as `consult-mcp`; Dockerfile for the HTTP mode.

## Engineering
- [ ] Coverage report in CI, plus type checking (pyright).
- [ ] A smoke test of the Inspector run in CI.
