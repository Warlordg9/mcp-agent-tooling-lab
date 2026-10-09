"""Генерирует таблицы отчёта (report/table_*.tex) из experiment/results/*.csv.

Запускать после исполнения experiment/analysis.ipynb.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiment" / "results"
OUT = ROOT / "report"


def pct(x: float) -> str:
    return f"{100 * x:.0f}"


def ci_pct(m: float, lo: float, hi: float) -> str:
    return f"{pct(m)} [{pct(lo)};\\,{pct(hi)}]"


def thousands(x: float) -> str:
    return f"{x:,.0f}".replace(",", r"\,")


def ci_text_to_pct(s: str) -> str:
    """'0.70 [0.50; 0.90]' -> '70 [50; 90]'."""
    m, lo, hi = map(float, re.findall(r"[\d.]+", s))
    return ci_pct(m, lo, hi)


def table_a() -> None:
    s = pd.read_csv(RES / "part_a_summary.csv")
    rows = [r"\begin{tabular}{rcccrr}\toprule",
            r"$N$ & точность A & точность B & Recall@5 (B) & \multicolumn{2}{c}{вход. токенов: A / B} \\ \midrule"]
    for n in sorted(s.N.unique()):
        a = s[(s.N == n) & (s.variant == "A")].iloc[0]
        b = s[(s.N == n) & (s.variant == "B")].iloc[0]
        rows.append(f"{n} & {ci_pct(a.accuracy, a.acc_lo, a.acc_hi)} & {ci_pct(b.accuracy, b.acc_lo, b.acc_hi)} & "
                    f"{ci_pct(b.recall5, b.rec_lo, b.rec_hi)} & {thousands(a.mean_input_tokens)} & {thousands(b.mean_input_tokens)} \\\\")
    rows.append(r"\bottomrule\end{tabular}")
    (OUT / "table_a.tex").write_text("\n".join(rows), encoding="utf-8")


def table_b() -> None:
    b = pd.read_csv(RES / "part_b_loops.csv", index_col=0)
    fm = pd.read_csv(RES / "part_b_failure_modes.csv", index_col=0)
    rows = [r"\begin{tabular}{lcccrrcc}\toprule",
            r"Условие (20 задач) & петля, \% & успех, \% & шагов & токенов & guard & выдуманный slot\_id & без брони \\ \midrule"]
    for name, r in b.iterrows():
        f = fm.loc[name]
        rows.append(f"{name} & {ci_text_to_pct(r['доля с петлёй'])} & {ci_text_to_pct(r['успех'])} & "
                    f"{float(r['шагов LLM (ср.)']):.1f} & {thousands(float(r['токенов (ср.)']))} & {int(r['срабатываний guard'])} & "
                    f"{pct(f['выдуманный slot_id'])}\\,\\% & {pct(f['нет ни одной брони'])}\\,\\% \\\\")
    rows.append(r"\bottomrule\end{tabular}")
    (OUT / "table_b.tex").write_text("\n".join(rows), encoding="utf-8")


if __name__ == "__main__":
    table_a()
    table_b()
    print((OUT / "table_a.tex").read_text(encoding="utf-8"))
    print((OUT / "table_b.tex").read_text(encoding="utf-8"))
