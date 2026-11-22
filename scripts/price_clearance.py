# Lesson 37: clearance markdowns - discount just enough to sell out; the outlet price sets a floor
import polars as pl
import numpy as np

WEEKS, E, SALVAGE = 6, -1.2, 0.10
grid = np.round(np.arange(0, 0.71, 0.05), 2)


def best_discount(base_week, stock):
    demand = WEEKS * base_week * (1 - grid) ** E
    sold = np.minimum(stock, demand)
    money = sold * (1 - grid) + (stock - sold) * SALVAGE
    i = money.argmax()
    return grid[i], money[i], money[0]


for s in [50, 120, 200]:
    d, m, m0 = best_discount(10, s)
    print(f"Example item (sells 10/week), stock {s}: best {d:.0%}, money {m:.1f} vs no discount {m0:.1f}")

tx = pl.scan_parquet("data/clean/transactions.parquet")
base = (
    tx.filter(pl.col("sale_date").is_between(pl.date(2020, 8, 1), pl.date(2020, 8, 28)))
    .group_by("article_id").agg((pl.len() / 4).alias("base_week"))
    .filter(pl.col("base_week") >= 5).sort("article_id").collect()
)
assert base.height == 9320

rng = np.random.default_rng(37)
stock = (base["base_week"].to_numpy() * WEEKS * rng.uniform(0.8, 3.0, base.height)).round()
res = [best_discount(b, s) for b, s in zip(base["base_week"].to_numpy(), stock)]
plan = base.with_columns(
    pl.Series("stock", stock),
    pl.Series("best_discount", [r[0] for r in res]),
    pl.Series("money", [r[1] for r in res]),
    pl.Series("money_no_disc", [r[2] for r in res]),
)
print(plan.group_by("best_discount").agg(pl.len().alias("items")).sort("best_discount"))

# Compare 3 strategies: no discount, flat 50% for everything, smart per-item discount
def money_at(d, base_week, stock):
    sold = np.minimum(stock, WEEKS * base_week * (1 - d) ** E)
    return sold * (1 - d) + (stock - sold) * SALVAGE

bw = base["base_week"].to_numpy()
none_ = money_at(0.0, bw, stock).sum()
flat50 = money_at(0.5, bw, stock).sum()
smart = plan["money"].sum()
print(f"No discount:   {none_:,.0f}")
print(f"Flat 50% off:  {flat50:,.0f}  ({flat50 / none_ - 1:+.1%})")
print(f"Smart per item: {smart:,.0f}  ({smart / none_ - 1:+.1%})")
plan.write_parquet("data/clean/clearance_plan.parquet")