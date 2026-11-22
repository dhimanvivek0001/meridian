# Simulated marketing mix: real daily sales as base + 4 channels with planted adstock and saturation
# Version 2: social and email spend now VARY, so the model can tell their effects apart
import polars as pl
import numpy as np

rng = np.random.default_rng(21)

daily = (
    pl.scan_parquet("data/clean/transactions.parquet")
    .group_by("sale_date").agg(pl.len().alias("base_items"))
    .sort("sale_date").collect()
)
n = daily.height
day = np.arange(n)
base = daily["base_items"].to_numpy().astype(float)

# 1. Daily spend in euros
spend = {
    "tv":     np.where((day // 14) % 2 == 0, rng.uniform(40000, 60000, n), 0.0),                        # 2 weeks on, 2 weeks off
    "social": np.where(rng.random(n) < 0.5, rng.uniform(15000, 25000, n), rng.uniform(0, 4000, n)),     # high/low days
    "search": 0.25 * base * rng.uniform(0.8, 1.2, n),                                                    # follows demand
    "email":  np.where(rng.random(n) < 0.25, 5000.0, 0.0),                                               # random days, ~2 a week
}

# 2. Planted truth: (echo decay, saturation point k, max extra items per day)
TRUTH = {"tv": (0.7, 150000, 6000), "social": (0.3, 15000, 3000),
         "search": (0.1, 12000, 4000), "email": (0.0, 5000, 1500)}

def adstock(x, decay):
    out, carry = np.zeros(len(x)), 0.0
    for i, v in enumerate(x):
        carry = v + decay * carry          # today's spend + what's left of the echo
        out[i] = carry
    return out

def saturate(x, k):
    return 1 - np.exp(-x / k)              # 0 = no effect, close to 1 = fully saturated

# 3. Each channel's true extra items, then total simulated sales
contrib = {c: TRUTH[c][2] * saturate(adstock(spend[c], TRUTH[c][0]), TRUTH[c][1]) for c in spend}
sales = base + sum(contrib.values()) + rng.normal(0, 1500, n)

sim = daily.select("sale_date").with_columns(
    *[pl.Series(f"spend_{c}", spend[c]) for c in spend],
    *[pl.Series(f"true_{c}", contrib[c]) for c in spend],
    pl.Series("sales", sales),
)
sim.write_parquet("data/clean/sim_mmm.parquet")

print(f"{n} days. Average daily sales {sales.mean():,.0f} items")
print("channel   total spend €   true extra items   true items per €1,000")
for c in spend:
    print(f"{c:8s} {spend[c].sum():>14,.0f} {contrib[c].sum():>17,.0f} {contrib[c].sum()/spend[c].sum()*1000:>16.1f}")