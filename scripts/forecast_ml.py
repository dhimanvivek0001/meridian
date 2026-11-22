# Lesson 39: global LightGBM forecaster across product groups vs seasonal baseline
import polars as pl
import numpy as np
from lightgbm import LGBMRegressor

arts = pl.read_parquet("data/parquet/articles.parquet")
tx = pl.scan_parquet("data/clean/transactions.parquet")
g = (
    tx.join(arts.lazy().select(["article_id", "product_group_name"]), on="article_id")
    .with_columns(pl.col("sale_date").dt.truncate("1w").alias("week"))
    .group_by(["product_group_name", "week"]).agg(pl.len().alias("units"))
    .collect()
)
weeks = sorted(g["week"].unique().to_list())[1:-1]
assert len(weeks) == 104
grid = pl.DataFrame({"week": weeks}).join(g.select("product_group_name").unique(), how="cross")
g = (
    grid.join(g, on=["product_group_name", "week"], how="left")
    .with_columns(pl.col("units").fill_null(0))
    .sort(["product_group_name", "week"])
)

big = g.group_by("product_group_name").agg(pl.col("units").sum()).filter(pl.col("units") >= 50000)["product_group_name"]
g = g.filter(pl.col("product_group_name").is_in(big.implode()))
g = g.with_columns(
    pl.col("units").cast(pl.Float64).log1p().alias("y"),
    pl.col("product_group_name").cast(pl.Categorical).to_physical().alias("grp"),
    pl.col("week").dt.week().alias("woy"),
)
g = g.with_columns([pl.col("y").shift(k).over("product_group_name").alias(f"lag{k}") for k in [8, 9, 10, 11, 52, 53]])
g.write_parquet("data/clean/group_weekly.parquet")

test_weeks = weeks[-8:]
train = g.filter(~pl.col("week").is_in(test_weeks) & pl.col("lag53").is_not_null())
test = g.filter(pl.col("week").is_in(test_weeks))
assert (big.len(), train.height, test.height) == (10, 430, 80)

feats = ["lag8", "lag9", "lag10", "lag11", "lag52", "lag53", "woy", "grp"]
model = LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=15,
                      min_child_samples=10, random_state=42, verbose=-1)
model.fit(train.select(feats).to_numpy(), train["y"].to_numpy(), categorical_feature=[7])
test = test.with_columns(
    pl.Series("ml", np.expm1(model.predict(test.select(feats).to_numpy())).clip(0)),
    (pl.col("lag52").exp() - 1).alias("seasonal"),
    pl.col("units").cast(pl.Float64),
)


def wape(a, f):
    return np.abs(a - f).sum() / a.sum()


a = test["units"].to_numpy()
print(f"Per group:     seasonal {wape(a, test['seasonal'].to_numpy()):.1%}   ML {wape(a, test['ml'].to_numpy()):.1%}")
tot = test.group_by("week").agg(pl.col("units", "seasonal", "ml").sum()).sort("week")
a2 = tot["units"].to_numpy()
print(f"Company total: seasonal {wape(a2, tot['seasonal'].to_numpy()):.1%}   ML {wape(a2, tot['ml'].to_numpy()):.1%}")