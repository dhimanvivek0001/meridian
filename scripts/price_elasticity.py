# Lesson 35: regression elasticity is fooled by reactive pricing; event study shows why
import polars as pl
import numpy as np

tx = pl.scan_parquet("data/clean/transactions.parquet")
weekly = (
    tx.with_columns(pl.col("sale_date").dt.truncate("1w").alias("week"))
    .group_by(["article_id", "week"])
    .agg(pl.len().alias("units"), pl.col("price_index").mean().alias("avg_price"))
    .collect()
)
assert weekly.height == 2210899

# 1. Regression: item + week normals removed, item age as a clue
weekly = weekly.with_columns(
    pl.col("units").log().alias("log_units"),
    (pl.col("avg_price") / pl.col("avg_price").max().over("article_id")).log().alias("log_price"),
    ((pl.col("week") - pl.col("week").min().over("article_id")).dt.total_days() / 7 + 1).log().alias("log_age"),
)


def demean(df, cols, rounds=5):
    for _ in range(rounds):
        df = df.with_columns([pl.col(c) - pl.col(c).mean().over("article_id") for c in cols])
        df = df.with_columns([pl.col(c) - pl.col(c).mean().over("week") for c in cols])
    return df


d = demean(weekly, ["log_units", "log_price", "log_age"])
X = d.select(["log_price", "log_age"]).to_numpy()
y = d["log_units"].to_numpy()
coef, *_ = np.linalg.lstsq(X, y, rcond=None)
print(f"Regression elasticity: {coef[0]:.2f} (wrong sign = reactive pricing)   Age effect: {coef[1]:.2f}")

# 2. Event study: sales around the first markdown (>15% off)
w = weekly.with_columns(
    (1 - pl.col("avg_price") / pl.col("avg_price").max().over("article_id")).alias("discount"),
    (pl.col("units") / pl.col("units").mean().over("article_id")).alias("lift"),
)
first_md = w.filter(pl.col("discount") > 0.15).group_by("article_id").agg(pl.col("week").min().alias("md_week"))
ev = (
    w.join(first_md, on="article_id")
    .with_columns(((pl.col("week") - pl.col("md_week")).dt.total_days() // 7).alias("rel_week"))
    .filter(pl.col("rel_week").is_between(-4, 4))
    .group_by("rel_week")
    .agg(
        pl.len().alias("items"),
        pl.col("lift").mean().round(2).alias("avg_lift"),
        pl.col("discount").mean().round(2).alias("avg_discount"),
    )
    .sort("rel_week")
)
print(ev)
ev.write_csv("reports/markdown_event_study.csv")