# T-learner uplift model: two churn models (no voucher / voucher), uplift = difference
import polars as pl
import numpy as np
from lightgbm import LGBMClassifier

df = pl.read_parquet("data/clean/uplift_experiment.parquet")
names = ["days_since", "visits", "spend", "items", "online_share",
         "visits_4w", "visits_prev12w", "avg_gap", "overdue",
         "age", "FN", "club_active", "news_regular"]

# 1. Random half to train, half to test
rng = np.random.default_rng(5)
df = df.with_columns(pl.Series("is_test", rng.random(df.height) < 0.5))
train, test = df.filter(~pl.col("is_test")), df.filter(pl.col("is_test"))

# 2. Two models: one per group
def fit(d):
    m = LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15,
                       min_child_samples=200, random_state=42, verbose=-1)
    m.fit(d.select(names).to_numpy(), d["churned_after"].to_numpy())
    return m

model_c = fit(train.filter(pl.col("voucher") == 0))
model_t = fit(train.filter(pl.col("voucher") == 1))

# 3. Score the test half
X = test.select(names).to_numpy()
p_without = model_c.predict_proba(X)[:, 1]
p_with = model_t.predict_proba(X)[:, 1]
test = test.with_columns(pl.Series("uplift", p_without - p_with), pl.Series("risk", p_without))

# 4. Rank customers into 5 bands (1 = top 20%) and check the REAL voucher effect in each band
def by_band(col):
    t = test.with_columns(pl.col(col).rank("ordinal", descending=True).alias("r"))
    t = t.with_columns(((pl.col("r") - 1) * 5 // t.height + 1).alias("band"))
    return t.group_by("band").agg(
        ((pl.col("churned_after").filter(pl.col("voucher") == 0).mean()
          - pl.col("churned_after").filter(pl.col("voucher") == 1).mean()) * 100).round(1).alias("real_effect_pts"),
        (pl.col("persuadable").mean() * 100).round(0).alias("pct_persuadable"),
    ).sort("band")

print("Ranked by UPLIFT model (band 1 = highest predicted uplift):")
print(by_band("uplift"))
print("Ranked by CHURN RISK (band 1 = riskiest):")
print(by_band("risk"))