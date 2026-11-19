# Cohort retention: of customers who first bought in month X, what % bought again 1..6 months later?
import polars as pl

clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. First month each customer bought = their cohort
first = clean.group_by("customer_id").agg(pl.col("month").min().alias("cohort")).collect()
assert first.height == 1362281, "Number of buying customers changed"

# 2. Stick cohort on every receipt, then months since first purchase
sales = clean.join(first.lazy(), on="customer_id", how="left")
sales = sales.with_columns(
    ((pl.col("month").dt.year() - pl.col("cohort").dt.year()) * 12
     + (pl.col("month").dt.month() - pl.col("cohort").dt.month())).alias("months_since")
)

# 3. Cohorts Mar-Dec 2019 (skip the early 'diary' months), first 7 months, count different customers
ret = (
    sales
    .filter(pl.col("cohort").is_between(pl.date(2019, 3, 1), pl.date(2019, 12, 1)))
    .filter(pl.col("months_since") <= 6)
    .group_by("cohort", "months_since")
    .agg(pl.col("customer_id").n_unique().alias("customers"))
    .collect()
)

# 4. Turn counts into % of the cohort's starting size
ret = ret.with_columns(
    (pl.col("customers") / pl.col("customers").max().over("cohort") * 100).round(1).alias("pct")
)
assert ret.filter(pl.col("months_since") == 0)["pct"].min() == 100, "Month 0 should be 100%"

# 5. Grid: cohorts down, months across
table = ret.pivot(on="months_since", index="cohort", values="pct", sort_columns=True).sort("cohort")
print(table)
table.write_csv("reports/cohort_retention.csv")
print("Saved reports/cohort_retention.csv")