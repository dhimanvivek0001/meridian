# T-shirt deep dive: fewer designs on sale, or each design selling less? (before covid)
# items = designs x items_per_design
import polars as pl

art = pl.read_parquet("data/parquet/articles.parquet")
clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. List of T-shirt codes, then keep only T-shirt receipts
tshirt_lookup = art.filter(pl.col("product_type_name") == "T-shirt").select("article_id")
tshirts = clean.join(tshirt_lookup.lazy(), on="article_id", how="inner")

# 2. Sticky note: last_year / this_year
tshirts_labelled = tshirts.with_columns(
    pl.when(pl.col("month").is_between(pl.date(2018, 10, 1), pl.date(2019, 2, 1))).then(pl.lit("last_year"))
    .when(pl.col("month").is_between(pl.date(2019, 10, 1), pl.date(2020, 2, 1))).then(pl.lit("this_year"))
    .alias("period")
)

# 3. Count items (receipts) and designs (different codes) per period
summary = tshirts_labelled.filter(pl.col("period").is_not_null()).group_by("period").agg(
    pl.len().alias("items"),
    pl.col("article_id").n_unique().alias("designs"),
).collect()

# 4. Check: items must match Lesson 9 T-shirt numbers
items = dict(zip(summary["period"], summary["items"]))
assert items["last_year"] == 369475, "T-shirt last year does not match Lesson 9"
assert items["this_year"] == 253366, "T-shirt this year does not match Lesson 9"

# 5. Items per design
summary = summary.with_columns(
    (pl.col("items") / pl.col("designs")).round(1).alias("items_per_design")
).sort("period")

print(summary)
summary.write_csv("reports/tshirts_designs.csv")
print("Saved reports/tshirts_designs.csv")