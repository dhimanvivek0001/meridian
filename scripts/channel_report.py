# Channel split: store vs online, before covid and during covid (each vs same months a year earlier)
import polars as pl

clean = pl.scan_parquet("data/clean/transactions.parquet")

# 1. Sticky note: which period?
labelled = clean.with_columns(
    pl.when(pl.col("month").is_between(pl.date(2018, 10, 1), pl.date(2019, 2, 1))).then(pl.lit("before_ly"))
    .when(pl.col("month").is_between(pl.date(2019, 10, 1), pl.date(2020, 2, 1))).then(pl.lit("before_ty"))
    .when(pl.col("month").is_between(pl.date(2019, 3, 1), pl.date(2019, 8, 1))).then(pl.lit("covid_ly"))
    .when(pl.col("month").is_between(pl.date(2020, 3, 1), pl.date(2020, 8, 1))).then(pl.lit("covid_ty"))
    .alias("period")
)

# 2. Count items per channel per period
channel = (
    labelled
    .filter(pl.col("period").is_not_null())
    .group_by("sales_channel", "period")
    .agg(pl.len().alias("items"))
    .collect()
)

# 3. Grid + % change
table = channel.pivot(on="period", index="sales_channel", values="items")
table = table.with_columns(
    ((pl.col("before_ty") / pl.col("before_ly") - 1) * 100).round(1).alias("before_pct"),
    ((pl.col("covid_ty") / pl.col("covid_ly") - 1) * 100).round(1).alias("covid_pct"),
)

# 4. Check: store + online must equal Lesson 8 totals
assert table["before_ly"].sum() == 6232369, "before_ly total does not match Lesson 8"
assert table["covid_ty"].sum() == 8103650, "covid_ty total does not match Lesson 8"

print(table)
table.write_csv("reports/channel_split.csv")
print("Saved reports/channel_split.csv")