"""Проверка чисел задачи 1 (стоимость в токен-эквивалентах, p_in = 1)."""

S, D, h, T = 2_000, 55_000, 1_500, 40


def cost(alpha: float, S=S, D=D, h=h, T=T, exact=False) -> tuple[float, float, float]:
    prefix = alpha * (S + D) * T
    history = h * T * (T + 1) / 2 if exact else h * T**2 / 2
    return prefix, history, prefix + history


print("(б)")
for alpha in (1.0, 0.1):
    p, hist, c = cost(alpha)
    _, hist_e, c_e = cost(alpha, exact=True)
    print(f"  alpha={alpha}: C={c:,.0f} (префикс {p:,.0f}, история {hist:,.0f}), доля истории {hist / c:.2%}; "
          f"точная сумма: C={c_e:,.0f}, доля {hist_e / c_e:.2%}")

base = cost(0.1)[2]
print("  рычаги при alpha=0.1 (экономия от базы):")
print(f"    D -> 0          : {base - cost(0.1, D=0)[2]:,.0f} ({1 - cost(0.1, D=0)[2] / base:.1%})")
print(f"    D -> D/2        : {base - cost(0.1, D=D / 2)[2]:,.0f} ({1 - cost(0.1, D=D / 2)[2] / base:.1%})")
print(f"    alpha 0.1 -> 0  : {base - cost(0.0)[2]:,.0f} ({1 - cost(0.0)[2] / base:.1%})")
print(f"    h -> h/2        : {base - cost(0.1, h=h / 2)[2]:,.0f} ({1 - cost(0.1, h=h / 2)[2] / base:.1%})")

print("(в)")
d, s, k = 300, 500, 5
b_cost = s + k * d
n_min = next(n for n in range(1, 1000) if d * n > b_cost)
print(f"  A: {d}N, B: {s} + {k}*{d} = {b_cost}; B дешевле при N > {b_cost / d:.2f} -> N_min = {n_min}")
alpha = 0.1
n_cache = next(n for n in range(1, 10_000) if alpha * d * n > b_cost)
print(f"  (с кэшем alpha={alpha} для статичного списка A и некэшируемой выдачей B: N_min = {n_cache})")

print("(г)")
recall, a5 = 0.95, 0.90
print(f"  точность B = {recall} * {a5} = {recall * a5:.3f}; B перестаёт выигрывать при A(N) >= {recall * a5:.3f}")
