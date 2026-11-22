# Lesson 36: randomised price test recovers the true elasticity; discounts raise revenue but cut profit
import polars as pl
import numpy as np

tx = pl.scan_parquet("data/clean/transactions.parquet")
base = (
    tx.filter(pl.col("sale_date").is_between(pl.date(2020, 8, 1), pl.date(2020, 8, 28)))
    .group_by("article_id")
    .agg((pl.len() / 4).alias("base_week"))
    .filter(pl.col("base_week") >= 5)
    .sort("article_id")
    .collect()
)
assert base.height == 9320

rng = np.random.default_rng(36)
TRUE_E = -1.2
arms = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
test = base.with_columns(pl.Series("discount", rng.choice(arms, base.height)))
expected = test["base_week"].to_numpy() * (1 - test["discount"].to_numpy()) ** TRUE_E
test = test.with_columns(pl.Series("units", rng.poisson(expected)))

summary = (
    test.group_by("discount")
    .agg(pl.len().alias("items"), (pl.col("units").sum() / pl.col("base_week").sum()).round(3).alias("lift"))
    .sort("discount")
)
slope, _ = np.polyfit(np.log(1 - summary["discount"].to_numpy()), np.log(summary["lift"].to_numpy()), 1)
print(f"Elasticity from the test: {slope:.2f}  (truth -1.2, regression said +0.14)")

COST = 0.5
money = summary.with_columns(
    ((1 - pl.col("discount")) * pl.col("lift")).round(3).alias("revenue"),
    ((1 - pl.col("discount") - COST) * pl.col("lift")).round(3).alias("profit"),
)
print(money)
money.write_csv("reports/price_test_money.csv")