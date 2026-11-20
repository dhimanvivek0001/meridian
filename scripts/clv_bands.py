# Simple CLV: does last year's spend predict next year's? (Year 1 = before 23 Sep 2019, Year 2 = after)
import polars as pl

clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. Each customer's spend in Year 1 and Year 2
years = (
    clean
    .with_columns(
        pl.when(pl.col("sale_date") < pl.date(2019, 9, 23)).then(pl.lit("y1"))
        .otherwise(pl.lit("y2")).alias("year")
    )
    .group_by("customer_id")
    .agg(
        pl.col("price_index").filter(pl.col("year") == "y1").sum().alias("spend_y1"),
        pl.col("price_index").filter(pl.col("year") == "y2").sum().alias("spend_y2"),
    )
    .collect()
)
assert years.height == 1362281, "Customer count changed"

# 2. Year-1 buyers cut into 5 equal bands by Year-1 spend
y1_buyers = years.filter(pl.col("spend_y1") > 0).with_columns(
    pl.col("spend_y1").qcut(5, labels=["1 lowest", "2", "3", "4", "5 highest"]).alias("band")
)

# 3. Next-year value and comeback rate per band
clv = (
    y1_buyers
    .group_by("band")
    .agg(
        pl.len().alias("customers"),
        pl.col("spend_y1").mean().round(3).alias("avg_y1"),
        pl.col("spend_y2").mean().round(3).alias("avg_y2"),
        ((pl.col("spend_y2") > 0).mean() * 100).round(1).alias("pct_came_back"),
        pl.col("spend_y2").sum().alias("total_y2"),
    )
    .with_columns((pl.col("total_y2") / pl.col("total_y2").sum() * 100).round(1).alias("pct_of_y2_money"))
    .sort("band")
)

print(clv)
clv.write_csv("reports/clv_bands.csv")
print("Saved reports/clv_bands.csv")