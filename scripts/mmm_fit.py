# Fit an MMM twice (naive vs with a demand control) and compare with the planted truth
import polars as pl
import numpy as np
from scipy.optimize import minimize

sim = pl.read_parquet("data/clean/sim_mmm.parquet")
channels = ["tv", "social", "search", "email"]
S = {c: sim[f"spend_{c}"].to_numpy() for c in channels}
y = sim["sales"].to_numpy()
n = len(y)

# Controls every MMM has: intercept, trend, weekday, month
wd = sim["sale_date"].dt.weekday().to_numpy()
mo = sim["sale_date"].dt.month().to_numpy()
controls = ([np.ones(n), np.arange(n) / n]
            + [(wd == d).astype(float) for d in range(2, 8)]
            + [(mo == m).astype(float) for m in range(2, 13)])

# A demand signal (like Google Trends): real daily demand with a little noise
base = (pl.scan_parquet("data/clean/transactions.parquet").group_by("sale_date")
        .agg(pl.len().alias("n")).sort("sale_date").collect()["n"].to_numpy().astype(float))
search_trends = base * np.random.default_rng(99).uniform(0.95, 1.05, n)

def adstock(x, decay):
    out, carry = np.zeros(len(x)), 0.0
    for i, v in enumerate(x):
        carry = v + decay * carry
        out[i] = carry
    return out

def saturate(x, k):
    return 1 - np.exp(-x / k)

def fit(extra):
    def build(params):
        cols = [saturate(adstock(S[c], params[2*i]), np.exp(params[2*i + 1])) for i, c in enumerate(channels)]
        return np.column_stack(cols + controls + extra)

    def error(params):                                  # how badly this guess fits the sales
        X = build(params)
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        return ((y - X @ coef) ** 2).mean()

    start = np.ravel([[0.3, np.log(S[c][S[c] > 0].mean())] for c in channels])
    bounds = [(0.0, 0.95), (np.log(500), np.log(1e6))] * len(channels)
    best = minimize(error, start, bounds=bounds, method="L-BFGS-B")
    X = build(best.x)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {c: (coef[i] * X[:, i]).sum() / S[c].sum() * 1000 for i, c in enumerate(channels)}

naive = fit([])
fixed = fit([search_trends])
truth = {c: sim[f"true_{c}"].sum() / S[c].sum() * 1000 for c in channels}

print("items per €1,000   TRUTH    naive MMM   MMM + demand control")
for c in channels:
    print(f"{c:8s}         {truth[c]:6.1f}    {naive[c]:8.1f}    {fixed[c]:8.1f}")