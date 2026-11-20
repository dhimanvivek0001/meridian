# RFM segments: score every active customer (last 12 months) on Recency, Frequency, Monetary, then name groups
import polars as pl

clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. R, F, M per customer (last 12 months of data)
rfm = (
    clean
    .filter(pl.col("sale_date") >= pl.date(2019, 9, 23))
    .group_by("customer_id")
    .agg(
        pl.col("sale_date").max().alias("last_date"),
        pl.col("sale_date").n_unique().alias("frequency"),
        pl.col("price_index").sum().alias("monetary"),
    )
    .with_columns(
        (pl.date(2020, 9, 23) - pl.col("last_date")).dt.total_days().alias("recency")
    )
    .collect()
)

# 2. Scores 1-5 (cut-offs close to the 25/50/75% values from describe())
scored = rfm.with_columns(
    pl.when(pl.col("recency") <= 30).then(5)
    .when(pl.col("recency") <= 90).then(4)
    .when(pl.col("recency") <= 180).then(3)
    .when(pl.col("recency") <= 270).then(2)
    .otherwise(1).alias("R"),
    pl.when(pl.col("frequency") >= 11).then(5)
    .when(pl.col("frequency") >= 6).then(4)
    .when(pl.col("frequency") >= 3).then(3)
    .when(pl.col("frequency") == 2).then(2)
    .otherwise(1).alias("F"),
    pl.when(pl.col("monetary") > 1.0).then(5)
    .when(pl.col("monetary") > 0.49).then(4)
    .when(pl.col("monetary") > 0.20).then(3)
    .when(pl.col("monetary") > 0.08).then(2)
    .otherwise(1).alias("M"),
)

# 3. Named segments from R and F (order matters: first match wins)
scored = scored.with_columns(
    pl.when((pl.col("R") >= 4) & (pl.col("F") >= 4)).then(pl.lit("Champions"))
    .when((pl.col("R") >= 4) & (pl.col("F") == 1)).then(pl.lit("New"))
    .when((pl.col("R") >= 3) & (pl.col("F") >= 3)).then(pl.lit("Loyal"))
    .when((pl.col("R") <= 2) & (pl.col("F") >= 3)).then(pl.lit("At risk"))
    .when((pl.col("R") <= 2) & (pl.col("F") <= 2)).then(pl.lit("Lost"))
    .otherwise(pl.lit("Needs attention"))
    .alias("segment")
)

# 4. Size and money per segment
summary = (
    scored
    .group_by("segment")
    .agg(
        pl.len().alias("customers"),
        pl.col("monetary").sum().alias("spend"),
    )
    .with_columns(
        (pl.col("customers") / pl.col("customers").sum() * 100).round(1).alias("pct_customers"),
        (pl.col("spend") / pl.col("spend").sum() * 100).round(1).alias("pct_spend"),
        (pl.col("spend") / pl.col("customers")).round(2).alias("spend_each"),
    )
    .sort("pct_spend", descending=True)
)

# 5. Checks
assert summary["customers"].sum() == rfm.height, "Some customers have no segment"
assert scored["segment"].null_count() == 0, "Empty segment found"

print(summary)
summary.write_csv("reports/rfm_segments.csv")
scored.write_parquet("data/clean/customer_segments.parquet")
print("Saved reports/rfm_segments.csv and data/clean/customer_segments.parquet")