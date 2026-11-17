# Year-over-year report: compare each month's sales with the same month last year.
import polars as pl

clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. Items sold per month
monthly = clean.group_by("month").agg(pl.len().alias("items")).sort("month").collect()

# 2. Copy the table, moved forward 1 year = "last year's" numbers
last_year = monthly.with_columns(pl.col("month").dt.offset_by("1y")).rename({"items": "items_last_year"})

# 3. Put them side by side and calculate the % change
yoy = monthly.join(last_year, on="month", how="inner")
yoy = yoy.with_columns(((pl.col("items") / pl.col("items_last_year") - 1) * 100).round(1).alias("yoy_pct"))

# 4. Keep only full months (Sep 2018 and Sep 2020 are partial)
yoy = yoy.filter(pl.col("month").is_between(pl.date(2019, 10, 1), pl.date(2020, 8, 1)))

# Automatic check
assert yoy.height == 11, "Expected 11 full months"

# 5. Show and save
pl.Config.set_tbl_rows(30)
print(yoy)
print("Average year-over-year change:", round(yoy["yoy_pct"].mean(), 1), "%")

yoy.write_csv("reports/yoy_monthly.csv")
print("Saved reports/yoy_monthly.csv")