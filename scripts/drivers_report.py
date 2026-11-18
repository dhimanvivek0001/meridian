# Sales drivers report: is the drop caused by fewer customers, fewer visits, or smaller baskets?
import polars as pl

clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. Count items, customers and visits per month
kpi = clean.group_by("month").agg(
    pl.len().alias("items"),
    pl.col("customer_id").n_unique().alias("customers"),
    pl.struct("customer_id", "sale_date").n_unique().alias("visits"),
).sort("month").collect()

# 2. The 3 drivers
kpi = kpi.with_columns(
    (pl.col("visits") / pl.col("customers")).round(3).alias("visits_per_customer"),
    (pl.col("items") / pl.col("visits")).round(3).alias("items_per_visit"),
)

# 3. Last year's copy (+1 year)
ly = kpi.with_columns(pl.col("month").dt.offset_by("1y")).select(
    "month",
    pl.col("customers").alias("customers_ly"),
    pl.col("visits_per_customer").alias("vpc_ly"),
    pl.col("items_per_visit").alias("ipv_ly"),
)

# 4. Side by side, full months only, % change per driver
parts = kpi.join(ly, on="month").filter(
    pl.col("month").is_between(pl.date(2019, 10, 1), pl.date(2020, 8, 1))
).select(
    "month",
    ((pl.col("customers") / pl.col("customers_ly") - 1) * 100).round(1).alias("customers_pct"),
    ((pl.col("visits_per_customer") / pl.col("vpc_ly") - 1) * 100).round(1).alias("visits_pct"),
    ((pl.col("items_per_visit") / pl.col("ipv_ly") - 1) * 100).round(1).alias("basket_pct"),
)

assert parts.height == 11, "Expected 11 full months"

# 5. Show and save
pl.Config.set_tbl_rows(30)
print(parts)
print(parts.select(pl.exclude("month").mean().round(1)))
parts.write_csv("reports/drivers_monthly.csv")
print("Saved reports/drivers_monthly.csv")