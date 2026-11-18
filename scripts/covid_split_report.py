# Covid split: were product groups already falling BEFORE covid?
# Before = Oct-Feb, Covid = Mar-Aug. Each compared with the same months one year earlier.
import polars as pl

art = pl.read_parquet("data/parquet/articles.parquet")
clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. Lookup: product code -> product group (tiny groups become "Other")
main_groups = ["Garment Upper body", "Garment Lower body", "Garment Full body", "Accessories",
               "Underwear", "Shoes", "Swimwear", "Socks & Tights", "Nightwear"]
lookup = art.select(
    "article_id",
    pl.when(pl.col("product_group_name").is_in(main_groups))
      .then(pl.col("product_group_name"))
      .otherwise(pl.lit("Other"))
      .alias("product_group"),
)
sales = clean.join(lookup.lazy(), on="article_id", how="left")

# 2. Sticky note: which period is each sale in? (Septembers stay empty)
labelled = sales.with_columns(
    pl.when(pl.col("month").is_between(pl.date(2018, 10, 1), pl.date(2019, 2, 1))).then(pl.lit("before_last_year"))
    .when(pl.col("month").is_between(pl.date(2019, 10, 1), pl.date(2020, 2, 1))).then(pl.lit("before_this_year"))
    .when(pl.col("month").is_between(pl.date(2019, 3, 1), pl.date(2019, 8, 1))).then(pl.lit("covid_last_year"))
    .when(pl.col("month").is_between(pl.date(2020, 3, 1), pl.date(2020, 8, 1))).then(pl.lit("covid_this_year"))
    .alias("period")
)

# 3. Count each period per product group
by_group = labelled.group_by("product_group").agg(
    (pl.col("period") == "before_last_year").sum().alias("before_ly"),
    (pl.col("period") == "before_this_year").sum().alias("before_ty"),
    (pl.col("period") == "covid_last_year").sum().alias("covid_ly"),
    (pl.col("period") == "covid_this_year").sum().alias("covid_ty"),
).collect()
assert by_group.height == 10, "Expected 10 product groups"

# 4. % change before covid and during covid
by_group = by_group.with_columns(
    ((pl.col("before_ty") / pl.col("before_ly") - 1) * 100).round(1).alias("before_pct"),
    ((pl.col("covid_ty") / pl.col("covid_ly") - 1) * 100).round(1).alias("covid_pct"),
).sort("before_pct")

print(by_group)
by_group.write_csv("reports/covid_split.csv")
print("Saved reports/covid_split.csv")