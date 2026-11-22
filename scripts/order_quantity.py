# Lesson 41: how much to order - newsvendor rule vs simple plans (closes M7)
import polars as pl
import numpy as np

t = pl.read_parquet("data/clean/forecast_ranges.parquet")
g = pl.read_parquet("data/clean/group_weekly.parquet")
weeks = sorted(g["week"].unique().to_list())
train = g.filter(~pl.col("week").is_in(weeks[-8:]) & pl.col("lag53").is_not_null())
r = (train["y"] - train["lag52"]).to_numpy()

PRICE, COST, SALVAGE = 1.0, 0.5, 0.1
short = PRICE - COST          # lost profit per missed sale
left = COST - SALVAGE         # loss per leftover item
level = short / (short + left)
print(f"Order level: {level:.0%}  ->  order {np.exp(np.quantile(r, level)):.2f}x last year")

actual = t["units"].to_numpy()
last = np.expm1(t["lag52"].to_numpy())


def profit(order):
    sold = np.minimum(order, actual)
    return (PRICE * sold - COST * order + SALVAGE * (order - sold)).sum()


plans = {
    "perfect (knew the future)": actual,
    "order = last year": last,
    "order = high (90th pct)": t["high2"].to_numpy(),
    f"newsvendor ({level:.0%} level)": last * np.exp(np.quantile(r, level)),
}
best = profit(actual)
for name, order in plans.items():
    p = profit(order)
    print(f"{name:28s} profit {p:>10,.0f}  ({p / best:.0%} of perfect)")