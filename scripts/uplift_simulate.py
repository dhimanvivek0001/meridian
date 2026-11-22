# Uplift experiment (simulated): the voucher works much better for online light shoppers
import polars as pl
import numpy as np

rng = np.random.default_rng(11)

aud = pl.read_csv("data/exports/winback_voucher.csv").select("external_id")
feats = pl.read_parquet("data/clean/churn_test_v2.parquet")
df = aud.join(feats, left_on="external_id", right_on="customer_id", how="inner")

# 1. Coin flip
df = df.with_columns(pl.Series("voucher", (rng.random(df.height) < 0.5).astype(int)))

# 2. Planted truth: who is persuadable?
df = df.with_columns(
    ((pl.col("online_share") >= 0.5) & (pl.col("visits") <= 4)).alias("persuadable"),
)
df = df.with_columns(
    pl.when(pl.col("persuadable")).then(0.35).otherwise(0.05).alias("true_save_rate")
)

# 3. Outcome: in the voucher group, a would-be churner stays with their true save rate
lucky = pl.Series(rng.random(df.height)) < df["true_save_rate"]
df = df.with_columns(
    pl.when((pl.col("voucher") == 1) & (pl.col("churned") == 1) & lucky)
      .then(0).otherwise(pl.col("churned")).alias("churned_after")
)

df.write_parquet("data/clean/uplift_experiment.parquet")
print(df.group_by("persuadable", "voucher").agg(
    pl.len().alias("customers"),
    (pl.col("churned_after").mean() * 100).round(1).alias("churn_pct"),
).sort("persuadable", "voucher"))