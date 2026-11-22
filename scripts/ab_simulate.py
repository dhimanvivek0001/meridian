# Simulated A/B test of the winback voucher (planted truth: voucher saves 20% of would-be churners)
import polars as pl
import numpy as np

TRUE_SAVE_RATE = 0.20                       # the planted truth our analysis must recover
rng = np.random.default_rng(42)             # fixed randomness, same result every run

aud = pl.read_csv("data/exports/winback_voucher.csv")                  # emailable winback audience
labels = pl.read_parquet("data/clean/churn_test.parquet").select("customer_id", "churned")
df = aud.join(labels, left_on="external_id", right_on="customer_id", how="inner")

# 1. Coin flip: half control, half voucher
df = df.with_columns(pl.Series("group", np.where(rng.random(df.height) < 0.5, "voucher", "control")))

# 2. Voucher effect: in the voucher group, each would-be churner is saved with 20% chance
lucky = pl.Series(rng.random(df.height) < TRUE_SAVE_RATE)
df = df.with_columns(
    pl.when((pl.col("group") == "voucher") & (pl.col("churned") == 1) & lucky)
      .then(0).otherwise(pl.col("churned")).alias("churned_after")
)

df.select("external_id", "group", "churned_after").write_parquet("data/clean/ab_results.parquet")
print(df.group_by("group").agg(
    pl.len().alias("customers"),
    (pl.col("churned_after").mean() * 100).round(2).alias("churn_pct"),
).sort("group"))