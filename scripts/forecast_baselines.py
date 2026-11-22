# Lesson 38: weekly sales, lazy forecasts and WAPE scoring (last 8 weeks hidden)
import polars as pl
import numpy as np

tx = pl.scan_parquet("data/clean/transactions.parquet")
wk = (
    tx.with_columns(pl.col("sale_date").dt.truncate("1w").alias("week"))
    .group_by("week").agg(pl.len().alias("units"))
    .sort("week").collect()
)
wk = wk.slice(1, wk.height - 2)          # drop half-full first and last weeks
assert wk.height == 104
wk.write_parquet("data/clean/weekly_units.parquet")

y = wk["units"].to_numpy().astype(float)  # float, NOT u32 (u32 can't go negative!)
actual = y[-8:]
train = y[:-8]

forecasts = {
    "naive (last week)": np.full(8, train[-1]),
    "avg of last 4 weeks": np.full(8, train[-4:].mean()),
    "seasonal (last year)": y[-60:-52],
}


def wape(f):
    return np.abs(actual - f).sum() / actual.sum()


for name, f in forecasts.items():
    print(f"{name:22s} WAPE {wape(f):.1%}")