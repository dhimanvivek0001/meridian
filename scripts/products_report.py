# Products report: which product groups lost the most sales (Oct 2019-Aug 2020 vs Oct 2018-Aug 2019)?
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

# 2. Attach the product group to every sale
sales = clean.join(lookup.lazy(), on="article_id", how="left")
assert sales.select(pl.col("product_group").null_count()).collect().item() == 0, "Some sales have no product"

# 3. Count each group last year vs this year
compare = sales.with_columns(
    pl.when(pl.col("month").is_between(pl.date(2018, 10, 1), pl.date(2019, 8, 1))).then(pl.lit("last_year"))
    .when(pl.col("month").is_between(pl.date(2019, 10, 1), pl.date(2020, 8, 1))).then(pl.lit("this_year"))
    .alias("period")
).group_by("product_group").agg(
    (pl.col("period") == "last_year").sum().cast(pl.Int64).alias("items_last_year"),
    (pl.col("period") == "this_year").sum().cast(pl.Int64).alias("items_this_year"),
).collect()

# 4. Change, biggest loss first
compare = compare.with_columns(
    (pl.col("items_this_year") - pl.col("items_last_year")).alias("change_items"),
    ((pl.col("items_this_year") / pl.col("items_last_year") - 1) * 100).round(1).alias("change_pct"),
).sort("change_items")

print(compare)
compare.write_csv("reports/products_change.csv")
print("Saved reports/products_change.csv")