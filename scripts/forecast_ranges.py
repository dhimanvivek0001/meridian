# Lesson 40: forecast ranges - quantile LightGBM (overconfident) vs past-miss range (honest)
import polars as pl
import numpy as np
from lightgbm import LGBMRegressor

g = pl.read_parquet("data/clean/group_weekly.parquet")
weeks = sorted(g["week"].unique().to_list())
test_weeks = weeks[-8:]
train = g.filter(~pl.col("week").is_in(test_weeks) & pl.col("lag53").is_not_null())
test = g.filter(pl.col("week").is_in(test_weeks))
assert (train.height, test.height) == (430, 80)

feats = ["lag8", "lag9", "lag10", "lag11", "lag52", "lag53", "woy", "grp"]
X, y = train.select(feats).to_numpy(), train["y"].to_numpy()
Xt = test.select(feats).to_numpy()
preds = {}
for q in [0.1, 0.5, 0.9]:
    m = LGBMRegressor(objective="quantile", alpha=q, n_estimators=300, learning_rate=0.05,
                      num_leaves=15, min_child_samples=10, random_state=42, verbose=-1)
    m.fit(X, y, categorical_feature=[7])
    preds[q] = np.expm1(m.predict(Xt)).clip(0)

# Past-miss range: how far "same week last year" was off during training
r = (train["y"] - train["lag52"]).to_numpy()
lo_r, hi_r = np.quantile(r, [0.1, 0.9])
print(f"Past misses: 10% of weeks below {np.exp(lo_r):.2f}x last year, 10% above {np.exp(hi_r):.2f}x")

test = test.with_columns(
    pl.Series("low", preds[0.1]), pl.Series("mid", preds[0.5]), pl.Series("high", preds[0.9]),
    ((pl.col("lag52") + lo_r).exp() - 1).alias("low2"),
    ((pl.col("lag52") + hi_r).exp() - 1).alias("high2"),
    pl.col("units").cast(pl.Float64),
)
for name, lo, hi in [("Quantile model", "low", "high"), ("Past-miss range", "low2", "high2")]:
    inside = ((test["units"] >= test[lo]) & (test["units"] <= test[hi])).mean()
    width = ((test[hi] - test[lo]) / test["units"]).mean()
    print(f"{name:16s} inside {inside:.0%} (target 80%), width {width:.0%} of sales")

test.write_parquet("data/clean/forecast_ranges.parquet")