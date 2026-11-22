# Lesson 47: "looks like what you bought" - visually similar items as a 4th candidate source, then re-rank
from datetime import date, timedelta

import numpy as np
import polars as pl
from lightgbm import LGBMRanker

SEED = 47
np.random.seed(SEED)
tx = pl.scan_parquet("data/clean/transactions.parquet")
ages = pl.read_parquet("data/clean/customers.parquet").select(["customer_id", "age"])
N_POP, N_PARTNERS, N_VIS = 50, 5, 5
BASE = ["is_own", "is_partner", "is_pop", "own_n", "own_days", "pair_n", "pair_links",
        "pop_1w", "pop_prev_1w", "pop_4w", "pop_rank", "trend", "cust_lines", "cust_days", "age", "age_gap"]
FEATURES = BASE + ["is_vis", "vis_sim", "vis_links"]

# 1. Visual neighbours: for each photographed item, its 5 most similar photos (from Lesson 46)
e = pl.read_parquet("data/clean/image_embeddings.parquet")
ids, emb = e["article_id"].to_list(), e["emb"].to_numpy()
sim = emb @ emb.T
np.fill_diagonal(sim, -1)
nn = np.argsort(-sim, axis=1)[:, :N_VIS]
vis = pl.DataFrame({
    "article_id": np.repeat(ids, N_VIS),
    "article_id_v": np.array(ids)[nn.ravel()],
    "sim": sim[np.arange(len(ids))[:, None], nn].ravel(),
})
assert vis.height == len(ids) * N_VIS
print(f"Visual neighbour table: {len(ids):,} items x {N_VIS} = {vis.height:,} rows, "
      f"median similarity {vis['sim'].median():.2f}")


def build(cut, n_pop=N_POP, use_vis=True):
    """Lesson 45 candidates + features + labels, optionally with the visual source."""
    d = lambda days: pl.lit(cut - timedelta(days=days))
    hist = tx.filter(pl.col("sale_date").is_between(d(28), d(1))).collect()
    label = (
        tx.filter(pl.col("sale_date").is_between(pl.lit(cut), pl.lit(cut + timedelta(days=6))))
        .select(["customer_id", "article_id"]).unique().with_columns(pl.lit(1).alias("label"))
        .collect()
    )
    buyers = label.select("customer_id").unique()
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
    top = pop.sort(["pop_1w", "article_id"], descending=[True, False]).head(n_pop).select("article_id")
    own = hist.group_by(["customer_id", "article_id"]).agg(
        pl.len().alias("own_n"), (pl.lit(cut) - pl.col("sale_date").max()).dt.total_days().alias("own_days")
    )
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
    # NEW source 4: photos that look like the customer's own items
    look = (
        own.select(["customer_id", "article_id"]).join(vis, on="article_id")
        .group_by(["customer_id", "article_id_v"]).agg(pl.col("sim").max().alias("vis_sim"), pl.len().alias("vis_links"))
        .rename({"article_id_v": "article_id"})
    )
    popc = buyers.join(top, how="cross")
    own_b, pair_b, look_b = (t.join(buyers, on="customer_id") for t in (own, pair, look))
    parts = [own_b.select(["customer_id", "article_id"]), pair_b.select(["customer_id", "article_id"]), popc]
    if use_vis:
        parts.append(look_b.select(["customer_id", "article_id"]))
    cand = (
        pl.concat(parts).unique()
        .join(own_b, on=["customer_id", "article_id"], how="left")
        .join(pair_b, on=["customer_id", "article_id"], how="left")
        .join(look_b, on=["customer_id", "article_id"], how="left")
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
            pl.col("vis_sim").is_not_null().cast(pl.Int8).alias("is_vis"),
            pl.col("is_pop").fill_null(0),
            pl.col("label").fill_null(0),
            (pl.col("age") - pl.col("item_age")).abs().alias("age_gap"),
        )
        .sort(["customer_id", "article_id"])
    )
    return cand, buyers.height


def recall(c):
    return c.group_by("customer_id").agg(pl.col("label").max())["label"].mean()


# 2. Recall on the test week: does the visual source add NEW correct items?
CUT = date(2020, 9, 16)
old, n_test = build(CUT, use_vis=False)
new, _ = build(CUT)
assert n_test == 68984
extra = (new.height - old.height) / n_test
fair, _ = build(CUT, n_pop=N_POP + round(extra), use_vis=False)  # same number of extra rows, but bestsellers
print(f"\nTest week candidate recall (ceiling for hit rate), {n_test:,} buyers:")
print(f"  L45 sources:                         {recall(old):.2%}  ({old.height / n_test:.1f} candidates per buyer)")
print(f"  + visually similar items:            {recall(new):.2%}  ({new.height / n_test:.1f} per buyer, +{extra:.1f})")
print(f"  control: + {round(extra)} more bestsellers instead: {recall(fair):.2%}  ({fair.height / n_test:.1f} per buyer)")
assert abs(recall(old) - 0.2396) < 0.0001, "must reproduce Lesson 45"

only_vis = new.filter((pl.col("is_vis") == 1) & (pl.col("is_own") + pl.col("is_partner") + pl.col("is_pop") == 0))
print(f"  Visual-only candidates: {only_vis.height:,} rows, {only_vis['label'].sum():,} were bought "
      f"({only_vis['label'].mean():.2%} vs {old['label'].mean():.2%} for L45 candidates)")
has_own = new.group_by("customer_id").agg(pl.col("is_own").max().alias("h"))
sub_ids = has_own.filter(pl.col("h") == 1).select("customer_id")
print(f"  Among the {sub_ids.height:,} buyers with history: recall "
      f"{recall(old.join(sub_ids, on='customer_id')):.2%} -> {recall(new.join(sub_ids, on='customer_id')):.2%}")

# 3. Re-train the Lesson 45 ranker (2 weeks) with the visual features and compare the hit rate
train = pl.concat([
    build(date(2020, 9, 2))[0].with_columns(pl.col("customer_id") + "_w1"),
    build(date(2020, 9, 9))[0].with_columns(pl.col("customer_id") + "_w2"),
]).sort(["customer_id", "article_id"])
fit = train.filter(pl.col("label").max().over("customer_id") == 1)
groups = fit.group_by("customer_id", maintain_order=True).len()["len"].to_numpy()
assert groups.sum() == fit.height
print(f"\nTraining on {len(groups):,} customer-weeks, {fit.height:,} rows")
model = LGBMRanker(
    objective="lambdarank", n_estimators=300, learning_rate=0.05, num_leaves=31,
    min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
    random_state=SEED, deterministic=True, force_row_wise=True, verbose=-1,
)
model.fit(fit.select(FEATURES).to_numpy(), fit["label"].to_numpy(), group=groups)
new = new.with_columns(pl.Series("score", model.predict(new.select(FEATURES).to_numpy())))
top = new.sort(["customer_id", "score"], descending=[False, True]).group_by("customer_id", maintain_order=True).head(12)
hit = top.group_by("customer_id").agg(pl.col("label").max())["label"].sum() / n_test
shown_vis = top.filter((pl.col("is_vis") == 1) & (pl.col("is_own") + pl.col("is_partner") + pl.col("is_pop") == 0))
print(f"Hit rate: L45 ranker 11.52% -> L47 ranker with visual source {hit:.2%} ({hit - 0.1152:+.2%} points)")
print(f"Visual-only items that made a top-12: {shown_vis.height:,} ({shown_vis['label'].sum():,} of them bought)")

imp = pl.DataFrame({"feature": FEATURES, "gain": model.booster_.feature_importance("gain")})
print(imp.with_columns((pl.col("gain") / pl.col("gain").sum()).round(3).alias("share"))
      .sort("share", descending=True).select(["feature", "share"]).head(8))
