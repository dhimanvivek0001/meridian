# Budget plan: use the fitted MMM to re-split the SAME daily budget, then check the gain against the truth
import polars as pl
import numpy as np
from scipy.optimize import minimize

sim = pl.read_parquet("data/clean/sim_mmm.parquet")
channels = ["tv", "social", "search", "email"]
S = {c: sim[f"spend_{c}"].to_numpy() for c in channels}
y = sim["sales"].to_numpy()
n = len(y)
wd = sim["sale_date"].dt.weekday().to_numpy()
mo = sim["sale_date"].dt.month().to_numpy()
controls = [np.ones(n), np.arange(n) / n]
controls += [(wd == d).astype(float) for d in range(2, 8)]
controls += [(mo == m).astype(float) for m in range(2, 13)]
base = (
    pl.scan_parquet("data/clean/transactions.parquet")
    .group_by("sale_date").agg(pl.len().alias("n"))
    .sort("sale_date").collect()["n"].to_numpy().astype(float)
)
controls.append(base * np.random.default_rng(99).uniform(0.95, 1.05, n))   # demand control


def adstock(x, decay):
    out, carry = np.zeros(len(x)), 0.0
    for i, v in enumerate(x):
        carry = v + decay * carry
        out[i] = carry
    return out


# 1. Fit the MMM (same as Lesson 32) and keep each channel's curve: (decay, k, beta)
def build(p):
    cols = []
    for i, c in enumerate(channels):
        cols.append(1 - np.exp(-adstock(S[c], p[2 * i]) / np.exp(p[2 * i + 1])))
    return np.column_stack(cols + controls)


def error(p):
    X = build(p)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return ((y - X @ coef) ** 2).mean()


start = np.ravel([[0.3, np.log(S[c][S[c] > 0].mean())] for c in channels])
limits = [(0.0, 0.95), (np.log(500), np.log(1e6))] * 4
best = minimize(error, start, bounds=limits, method="L-BFGS-B")
coef, *_ = np.linalg.lstsq(build(best.x), y, rcond=None)
fitted = {c: (best.x[2 * i], np.exp(best.x[2 * i + 1]), coef[i]) for i, c in enumerate(channels)}

truth = {
    "tv": (0.7, 150000, 6000),
    "social": (0.3, 15000, 3000),
    "search": (0.1, 12000, 4000),
    "email": (0.0, 5000, 1500),
}


# 2. Extra items per day if each channel gets a steady daily budget
def items(alloc, curves):
    total = 0.0
    for x, c in zip(alloc, channels):
        d, k, b = curves[c]
        total += b * (1 - np.exp(-x / ((1 - d) * k)))
    return total


current = np.array([S[c].mean() for c in channels])
TOTAL = current.sum()

# 3. Best split of the SAME total, each channel between 50% and 200% of today
plan = minimize(
    lambda a: -items(a, fitted),
    current,
    method="SLSQP",
    bounds=[(0.5 * x, 2.0 * x) for x in current],
    constraints=[{"type": "eq", "fun": lambda a: a.sum() - TOTAL}],
).x

print(f"Daily budget stays at EUR {TOTAL:,.0f}")
print("channel   today EUR/day   plan EUR/day   change")
for c, a, b in zip(channels, current, plan):
    print(f"{c:8s} {a:>13,.0f} {b:>14,.0f} {b - a:>+9,.0f}")

model_gain = items(plan, fitted) - items(current, fitted)
real_gain = items(plan, truth) - items(current, truth)
print(f"Extra items per day, model promises: {model_gain:+,.0f}")
print(f"Extra items per day, really (truth): {real_gain:+,.0f}")
print(f"Extra items per year, really: {real_gain * 365:+,.0f}")