# Lesson 34: price vs units - raw comparison is fooled by confounding, within-item is better
import polars as pl

tx = pl.scan_parquet("data/clean/transactions.parquet")
weekly = (
    tx.with_columns(pl.col("sale_date").dt.truncate("1w").alias("week"))
    .group_by(["article_id", "week"])
    .agg(pl.len().alias("units"), pl.col("price_index").mean().alias("avg_price"))
    .collect()
)
assert weekly.height == 2210899

weekly = weekly.with_columns(
    (1 - pl.col("avg_price") / pl.col("avg_price").max().over("article_id")).alias("discount"),
    (pl.col("units") / pl.col("units").mean().over("article_id")).alias("lift"),
)
bands = (
    weekly.with_columns(
        pl.col("discount").cut([0.05, 0.15, 0.30, 0.50],
                               labels=["0-5%", "5-15%", "15-30%", "30-50%", "50%+"]).alias("band")
    )
    .group_by("band")
    .agg(
        pl.len().alias("item_weeks"),
        pl.col("units").mean().round(1).alias("raw_avg_units"),
        pl.col("lift").mean().round(2).alias("lift_vs_own_normal"),
    )
    .sort("band")
)
print(bands)
bands.write_csv("reports/price_discount_bands.csv")