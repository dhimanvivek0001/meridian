# Lesson 42: recommender time machine + popularity baseline (same 12 bestsellers for everyone)
import polars as pl

tx = pl.scan_parquet("data/clean/transactions.parquet")
arts = pl.read_parquet("data/parquet/articles.parquet")
CUT = pl.date(2020, 9, 16)

test = (
    tx.filter(pl.col("sale_date") >= CUT)
    .group_by("customer_id").agg(pl.col("article_id").unique().alias("bought"))
    .collect()
)
assert test.height == 68984
test.write_parquet("data/clean/reco_test.parquet")

top12 = (
    tx.filter(pl.col("sale_date").is_between(pl.date(2020, 9, 9), pl.date(2020, 9, 15)))
    .group_by("article_id").agg(pl.len().alias("n"))
    .sort("n", descending=True).head(12)
    .collect()["article_id"].to_list()
)
res = (
    test.explode("bought")
    .with_columns(pl.col("bought").is_in(top12).alias("hit"))
    .group_by("customer_id")
    .agg(pl.col("hit").any().alias("any_hit"), pl.col("hit").sum().alias("n_hit"))
)
print(f"Buyers in test week: {test.height:,}")
print(f"Hit rate (bought 1+ of our 12): {res['any_hit'].mean():.2%}")
print(arts.filter(pl.col("article_id").is_in(top12)).select(["article_id", "prod_name", "product_type_name"]))