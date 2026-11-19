# Tops drill-down: which types of tops lost sales BEFORE covid?
# Oct 2019-Feb 2020 (this_year) vs Oct 2018-Feb 2019 (last_year)
import polars as pl

art = pl.read_parquet("data/parquet/articles.parquet")
clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. Card with tops only: code -> type
tops_lookup = art.filter(pl.col("product_group_name") == "Garment Upper body").select("article_id", "product_type_name")

# 2. Keep only receipts for tops (inner = drop everything not on the card)
tops = clean.join(tops_lookup.lazy(), on="article_id", how="inner")

# 3. Sticky note: last_year / this_year (other months stay empty)
tops_labelled = tops.with_columns(
    pl.when(pl.col("month").is_between(pl.date(2018, 10, 1), pl.date(2019, 2, 1))).then(pl.lit("last_year"))
    .when(pl.col("month").is_between(pl.date(2019, 10, 1), pl.date(2020, 2, 1))).then(pl.lit("this_year"))
    .alias("period")
)

# 4. Count per type
by_type = tops_labelled.group_by("product_type_name").agg(
    (pl.col("period") == "last_year").sum().cast(pl.Int64).alias("items_ly"),
    (pl.col("period") == "this_year").sum().cast(pl.Int64).alias("items_ty"),
).collect()

# 5. Check: totals must match Lesson 8 upper body numbers
assert by_type["items_ly"].sum() == 2850711, "Last year total does not match Lesson 8"
assert by_type["items_ty"].sum() == 2430128, "This year total does not match Lesson 8"

# 6. Change, biggest loss first
by_type = by_type.with_columns(
    (pl.col("items_ty") - pl.col("items_ly")).alias("change_items"),
    ((pl.col("items_ty") / pl.col("items_ly") - 1) * 100).round(1).alias("change_pct"),
).sort("change_items")

pl.Config.set_tbl_rows(30)
print(by_type)
by_type.write_csv("reports/tops_by_type.csv")
print("Saved reports/tops_by_type.csv")