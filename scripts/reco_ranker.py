# Lesson 45: combine candidate sources + LightGBM ranker (learns the slot order instead of a hand-written rule)
from datetime import date, timedelta

import numpy as np
import polars as pl
from lightgbm import LGBMRanker

SEED = 45
np.random.seed(SEED)
tx = pl.scan_parquet("data/clean/transactions.parquet")
ages = pl.read_parquet("data/clean/customers.parquet").select(["customer_id", "age"])
N_POP, N_PARTNERS = 50, 5
FEATURES = [
    "is_own", "is_partner", "is_pop", "own_n", "own_days", "pair_n", "pair_links",
    "pop_1w", "pop_prev_1w", "pop_4w", "pop_rank", "trend", "cust_lines", "cust_days", "age", "age_gap",
]


def build(cut):
    """Candidates + features + labels for the week starting at `cut`, using only data before `cut`."""
    d = lambda days: pl.lit(cut - timedelta(days=days))
    hist = tx.filter(pl.col("sale_date").is_between(d(28), d(1))).collect()
    label = (
        tx.filter(pl.col("sale_date").is_between(pl.lit(cut), pl.lit(cut + timedelta(days=6))))
        .select(["customer_id", "article_id"]).unique().with_columns(pl.lit(1).alias("label"))
        .collect()
    )
    buyers = label.select("customer_id").unique()

    # Item popularity: last week, the week before, last 4 weeks, and the average buyer age
    pop = (
        hist.join(ages, on="customer_id", how="left")
        .group_by("article_id").agg(
            pl.col("sale_date").filter(pl.col("sale_date") >= d(7)).len().alias("pop_1w"),
            pl.col("sale_date").filter(pl.col("sale_date").is_between(d(14), d(8))).len().alias("pop_prev_1w"),
            pl.len().alias("pop_4w"),
            pl.col("age").mean().alias("item_age"),
        )
        .with_columns(
            pl.col("pop_1w").rank("ordinal", descending=True).alias("pop_rank"),
            ((pl.col("pop_1w") + 1) / (pl.col("pop_prev_1w") + 1)).alias("trend"),
        )
    )
    top = pop.sort(["pop_1w", "article_id"], descending=[True, False]).head(N_POP).select("article_id")

    # Source 1: own items (buy-again)
    own = hist.group_by(["customer_id", "article_id"]).agg(
        pl.len().alias("own_n"), (pl.lit(cut) - pl.col("sale_date").max()).dt.total_days().alias("own_days")
    )
    # Source 2: partners of own items (Lesson 44, now top-5)
    basket = hist.select(["customer_id", "sale_date", "article_id"]).unique()
    partners = (
        basket.join(basket, on=["customer_id", "sale_date"], suffix="_p")
        .filter(pl.col("article_id") != pl.col("article_id_p"))
        .group_by(["article_id", "article_id_p"]).agg(pl.len().alias("n"))
        .filter(pl.col("n") >= 2)
        .sort(["article_id", "n", "article_id_p"], descending=[False, True, False])
        .group_by("article_id", maintain_order=True).head(N_PARTNERS)
    )
    pair = (
        own.select(["customer_id", "article_id"]).join(partners, on="article_id")
        .group_by(["customer_id", "article_id_p"]).agg(pl.col("n").max().alias("pair_n"), pl.len().alias("pair_links"))
        .rename({"article_id_p": "article_id"})
    )
    # Source 3: top-50 bestsellers for every buyer
    popc = buyers.join(top, how="cross")

    own_b, pair_b = own.join(buyers, on="customer_id"), pair.join(buyers, on="customer_id")
    cand = (
        pl.concat([own_b.select(["customer_id", "article_id"]), pair_b.select(["customer_id", "article_id"]), popc])
        .unique()
        .join(own_b, on=["customer_id", "article_id"], how="left")
        .join(pair_b, on=["customer_id", "article_id"], how="left")
        .join(popc.with_columns(pl.lit(1).alias("is_pop")), on=["customer_id", "article_id"], how="left")
        .join(pop, on="article_id", how="left")
        .join(
            hist.group_by("customer_id").agg(
                pl.len().alias("cust_lines"),
                (pl.lit(cut) - pl.col("sale_date").max()).dt.total_days().alias("cust_days"),
            ),
            on="customer_id", how="left",
        )
        .join(ages, on="customer_id", how="left")
        .join(label, on=["customer_id", "article_id"], how="left")
        .with_columns(
            pl.col("own_n").is_not_null().cast(pl.Int8).alias("is_own"),
            pl.col("pair_n").is_not_null().cast(pl.Int8).alias("is_partner"),
            pl.col("is_pop").fill_null(0),
            pl.col("label").fill_null(0),
            (pl.col("age") - pl.col("item_age")).abs().alias("age_gap"),
        )
        .sort(["customer_id", "article_id"])
    )
    return cand, buyers.height


# Two training weeks: with only one (9-15 Sep) the ranker scored 10.93% and LOST to Lesson 44 (too little data)
train_a, n_a = build(date(2020, 9, 2))
train_b, n_b = build(date(2020, 9, 9))
test, n_test = build(date(2020, 9, 16))
assert n_test == 68984, "same test buyers as Lessons 42-44"
# The same customer in two weeks must be two separate groups, so tag the week onto the id
train = pl.concat([
    train_a.with_columns(pl.col("customer_id") + "_w1"),
    train_b.with_columns(pl.col("customer_id") + "_w2"),
]).sort(["customer_id", "article_id"])
print(f"Train week 2-8 Sep:  {n_a:,} buyers, {train_a.height:,} candidate rows, {train_a['label'].sum():,} positives")
print(f"Train week 9-15 Sep: {n_b:,} buyers, {train_b.height:,} candidate rows, {train_b['label'].sum():,} positives")
print(f"Test week 16-22 Sep: {n_test:,} buyers, {test.height:,} candidate rows, {test['label'].sum():,} positives")


def recall(c):
    """Share of buyers with at least one bought item anywhere in their candidates = best possible hit rate."""
    return c.group_by("customer_id").agg(pl.col("label").max())["label"].mean()


print(f"Candidate recall (ceiling for hit rate): train {recall(train):.2%}, test {recall(test):.2%}")

# Lambdarank needs rows grouped by customer and only customers with at least one positive (others teach nothing)
fit = train.filter(pl.col("label").max().over("customer_id") == 1)
groups = fit.group_by("customer_id", maintain_order=True).len()["len"].to_numpy()
assert groups.sum() == fit.height
print(f"Training on {len(groups):,} customers with a positive, {fit.height:,} rows")

model = LGBMRanker(
    objective="lambdarank", n_estimators=300, learning_rate=0.05, num_leaves=31,
    min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
    random_state=SEED, deterministic=True, force_row_wise=True, verbose=-1,
)
model.fit(fit.select(FEATURES).to_numpy(), fit["label"].to_numpy(), group=groups)


def top12_hit(c, score_col):
    top = c.sort(["customer_id", score_col], descending=[False, True]).group_by("customer_id", maintain_order=True).head(12)
    return top.group_by("customer_id").agg(pl.col("label").max())["label"].sum() / n_test


test = test.with_columns(pl.Series("score", model.predict(test.select(FEATURES).to_numpy())))
# Hand rule on the SAME candidates, for a fair comparison: own (most bought) > partner (most baskets) > popularity
test = test.with_columns(
    (pl.col("is_own") * 1e9 + pl.col("own_n").fill_null(0) * 1e6
     + pl.col("is_partner") * 1e5 + pl.col("pair_n").fill_null(0) * 10 - pl.col("pop_rank").fill_null(9999) / 1e4).alias("rule")
)
rule, ranker = top12_hit(test, "rule"), top12_hit(test, "score")
print("\nHit rate on test week (12 items per buyer):")
print("  L42 popular only:              6.43%")
print("  L43 buy-again + popular:       10.65%")
print("  L44 + bought-together pairs:   11.37%")
print(f"  L45 hand rule, wider pool:     {rule:.2%}")
print(f"  L45 LightGBM ranker:           {ranker:.2%}")
print(f"  Ranker vs L44: {ranker - 0.1137:+.2%} points ({ranker / 0.1137 - 1:+.1%})")
assert ranker > 0.1137, "ranker must beat Lesson 44"

has_hist = test.group_by("customer_id").agg(pl.col("is_own").max().alias("h"))
for flag, name in [(1, "with 4-week history"), (0, "without history (bestsellers only)")]:
    ids = has_hist.filter(pl.col("h") == flag).select("customer_id")
    sub = test.join(ids, on="customer_id")
    k = ids.height
    print(f"  {name}: {k:,} buyers | rule {top12_hit(sub, 'rule') * n_test / k:.2%} | ranker {top12_hit(sub, 'score') * n_test / k:.2%}")

imp = pl.DataFrame({"feature": FEATURES, "gain": model.booster_.feature_importance("gain")})
imp = imp.with_columns((pl.col("gain") / pl.col("gain").sum()).alias("share")).sort("share", descending=True)
print("\nWhat the ranker leans on (share of total gain):")
print(imp.select(["feature", pl.col("share").round(3)]).head(8))
test.select(["customer_id", "article_id", "score"]).write_parquet("data/clean/reco_ranked.parquet")
