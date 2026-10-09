"""Собирает experiment/analysis.ipynb (исполнять: jupyter nbconvert --execute --inplace)."""

from pathlib import Path

import nbformat as nbf

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s))  # noqa: E731
code = lambda s: cells.append(nbf.v4.new_code_cell(s))  # noqa: E731

md("""# Задача 3. Выбор из N и петли — анализ сырых логов

Источники: `logs/part_a.jsonl` (каждый запуск выбора инструмента) и `logs/part_b.jsonl` (каждый эпизод агента).
Неудачные и незавершённые запуски **не выбрасываются**: они входят в знаменатель как ошибки.
Доверительные интервалы — 95 % перцентильный бутстрэп (10 000 повторов), ресэмплируются **запросы**
(для части B — задачи), а не отдельные запуски.""")

code("""import json, sys
from pathlib import Path
import numpy as np, pandas as pd, matplotlib.pyplot as plt
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'consult_mcp').is_dir())
sys.path.insert(0, str(ROOT))
from experiment.common import bootstrap_ci, RESULTS, CHAT_MODEL, EMBED_MODEL, NUM_CTX, TEMPERATURE
RESULTS.mkdir(parents=True, exist_ok=True)
A = pd.DataFrame([json.loads(l) for l in open(ROOT/'experiment/logs/part_a.jsonl', encoding='utf-8')])
queries = pd.DataFrame(json.load(open(ROOT/'experiment/data/queries.json', encoding='utf-8')))
pool = pd.DataFrame(json.load(open(ROOT/'experiment/data/tool_pool.json', encoding='utf-8')))
print('модель:', CHAT_MODEL, '| эмбеддинги:', EMBED_MODEL, '| num_ctx:', NUM_CTX, '| temperature:', TEMPERATURE)
print('пул:', pool.kind.value_counts().to_dict(), '| запросов:', len(queries))
print('записей в логе A:', len(A), '| ожидалось:', len(queries)*4*2*3)
print(A.groupby(['N','variant']).status.value_counts().unstack(fill_value=0))""")

md("## Часть A. Полнота лога и неудачные запуски")
code("""expected = pd.MultiIndex.from_product([queries.id, [5,20,50,100], ['A','B'], [1,2,3]], names=['query_id','N','variant','run'])
have = pd.MultiIndex.from_frame(A[['query_id','N','variant','run']])
missing = expected.difference(have)
print('отсутствующих запусков:', len(missing))
# отсутствующий запуск = незавершённый; добавляем его как ошибку, чтобы знаменатель был полным
if len(missing):
    A = pd.concat([A, pd.DataFrame([dict(zip(expected.names, m), status='missing', correct=False) for m in missing])])
A['correct'] = A['correct'].fillna(False).astype(bool)
A['no_tool_call'] = A.apply(lambda r: r.get('status')=='ok' and not (r.get('response') or {}).get('tool_calls'), axis=1)
print(A.groupby(['N','variant']).agg(runs=('correct','size'), failed=('status', lambda s: (s!='ok').sum()),
                                      no_tool_call=('no_tool_call','sum')))""")

md("## Часть A. Точность выбора и Recall@5 с бутстрэпом по запросам")
code("""rows = []
for (n, v), g in A.groupby(['N','variant']):
    per_q = g.groupby('query_id').correct.mean().reindex(queries.id).fillna(0).to_numpy()
    acc, lo, hi = bootstrap_ci(per_q)
    tok = g.loc[g.status=='ok','prompt_eval_count']
    row = dict(N=n, variant=v, accuracy=acc, acc_lo=lo, acc_hi=hi, runs=len(g),
               mean_input_tokens=tok.mean(), median_input_tokens=tok.median())
    if v == 'B':
        rec = g.drop_duplicates('query_id').set_index('query_id').recall_hit.reindex(queries.id).astype(float).to_numpy()
        r, rlo, rhi = bootstrap_ci(rec)
        row |= dict(recall5=r, rec_lo=rlo, rec_hi=rhi)
    rows.append(row)
summary = pd.DataFrame(rows)
summary.to_csv(RESULTS/'part_a_summary.csv', index=False)
pd.options.display.float_format = '{:.3f}'.format
summary""")

code("""fig, ax = plt.subplots(figsize=(6.4, 3.8))
for v, color, label, dx in [('A', '#1f77b4', 'A: все N описаний', 0.95), ('B', '#d62728', 'B: top-5 по эмбеддингам', 1.0)]:
    s = summary[summary.variant==v].sort_values('N')
    ax.errorbar(s.N*dx, s.accuracy, yerr=[s.accuracy-s.acc_lo, s.acc_hi-s.accuracy], marker='o', capsize=4, color=color, label=label)
s = summary[summary.variant=='B'].sort_values('N')
ax.errorbar(s.N*1.05, s.recall5, yerr=[s.recall5-s.rec_lo, s.rec_hi-s.recall5], marker='s', ls='--', capsize=4, color='gray', label='Recall@5 поиска')
ax.set_xscale('log'); ax.set_xticks([5,20,50,100]); ax.set_xticklabels([5,20,50,100])
ax.set_xlabel('N — число инструментов в пуле'); ax.set_ylabel('доля'); ax.set_ylim(0.5, 1.02)
ax.set_title(f'Точность выбора ({CHAT_MODEL}), 30 запросов × 3 запуска, 95% CI'); ax.grid(alpha=.3); ax.legend(fontsize=8, loc='lower left')
fig.tight_layout(); fig.savefig(RESULTS/'accuracy_vs_N.png', dpi=200); fig.savefig(RESULTS/'accuracy_vs_N.pdf')""")

md("### Таблица токенов (среднее число входных токенов на запрос, `prompt_eval_count` из Ollama)")
code("""tokens = summary.pivot(index='N', columns='variant', values='mean_input_tokens')
tokens['B / A'] = tokens['B'] / tokens['A']
tokens.to_csv(RESULTS/'part_a_tokens.csv'); tokens.round({'A': 0, 'B': 0, 'B / A': 2})""")

md("### Разрез: запросы к своим инструментам и «почти похожие» запросы (gold — отвлекающий инструмент)")
code("""A['gold_kind'] = A.gold.map(pool.set_index('name').kind)
by_kind = A.groupby(['gold_kind','N','variant']).correct.mean().unstack('variant')
by_kind.to_csv(RESULTS/'part_a_by_kind.csv'); by_kind""")

code("""# Какие инструменты модель выбирает по ошибке (все N, оба варианта)
wrong = A[(~A.correct) & (A.status=='ok')]
pd.crosstab(wrong.gold, wrong.selected.fillna('<нет вызова>')).stack().loc[lambda s: s>0].sort_values(ascending=False).head(15)""")

md("## Часть B. Петли: три условия")
code("""B = pd.DataFrame([json.loads(l) for l in open(ROOT/'experiment/logs/part_b.jsonl', encoding='utf-8')])
tasks = json.load(open(ROOT/'experiment/data/loop_tasks.json', encoding='utf-8'))
print('эпизодов:', len(B), '| ожидалось:', 4*len(tasks), '| статусы:', B.status.value_counts().to_dict())
B['success'] = B['success'].fillna(False).astype(bool)
def ci(x):
    m, lo, hi = bootstrap_ci(np.asarray(x, dtype=float)); return f'{m:.2f} [{lo:.2f}; {hi:.2f}]'
order = ['no_guard', 'guard', 'hint', 'stable']
names = {'no_guard': 'пустой ответ, без LoopGuard', 'guard': 'пустой ответ + LoopGuard (3/6)',
         'hint': 'ответ с подсказкой, без LoopGuard', 'stable': 'контроль: стабильный инструмент'}
table = pd.DataFrame({c: {
    'эпизодов': len(g), 'доля с петлёй': ci(g.loop.fillna(True)), 'успех': ci(g.success),
    'шагов LLM (ср.)': g.turns.mean(), 'вызовов инструментов (ср.)': g.tool_calls.mean(),
    'токенов (ср.)': g.tokens.mean(), 'срабатываний guard': int(g.guard_triggers.sum()),
    'окончание': g.end.value_counts().to_dict()} for c, g in B.groupby('condition')}).T.loc[order]
table.index = [names[i] for i in table.index]
table.to_csv(RESULTS/'part_b_loops.csv'); table""")

md("""### Режимы отказа

Пустой ответ ломает агента не только петлями. Для каждого эпизода считаем: была ли попытка записать
**несуществующий слот** (slot_id выдуман моделью: ошибка «не найден»), закончился ли эпизод **без записи**
(отказ или преждевременный ответ), и сколько пустых или «ничего не найдено» ответов поиска получил агент.""")
code("""def modes(r):
    tr = r.trace if isinstance(r.trace, list) else []
    calls = [s for s in tr if 'tool' in s]
    booked = any(s['tool'] == 'consult_book' and not s['is_error'] for s in calls)
    return pd.Series({
        'выдуманный slot_id': any(s['tool'] == 'consult_book' and 'не найден' in (s['result'] or '') for s in calls),
        'нет ни одной брони': not booked,
        'пустых/«ничего не найдено» ответов поиска': sum(s['tool'] == 'consult_search_slots' and (s['result'] == '' or s['result'].startswith('Ничего не найдено')) for s in calls),
    })
fm = B.join(B.apply(modes, axis=1)).groupby('condition')[['выдуманный slot_id', 'нет ни одной брони', 'пустых/«ничего не найдено» ответов поиска']].mean().loc[order]
fm.index = [names[i] for i in fm.index]
fm.to_csv(RESULTS/'part_b_failure_modes.csv'); fm.round(2)""")

code("""# Типичная петля из лога (первая найденная в условии no_guard)
ep = B[(B.condition=='no_guard') & (B.loop==True)].head(1)
for _, r in ep.iterrows():
    print(r.task_id)
    for s in r.trace[:10]:
        print(' ', s.get('turn'), s.get('tool'), json.dumps(s.get('args'), ensure_ascii=False)[:90], '->', repr((s.get('result') or s.get('final_text') or '')[:60]))""")

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3"}})
nbf.write(nb, Path(__file__).with_name("analysis.ipynb"))
print("written")
