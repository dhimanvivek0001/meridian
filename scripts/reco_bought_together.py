# Lesson 44: "bought together" recommender - own recent items, then their top-3 basket partners, then bestsellers
import numpy as np
import polars as pl

np.random.seed(44)
tx = pl.scan_parquet("data/clean/transactions.parquet")
test = pl.read_parquet("data/clean/reco_test.parquet")
assert test.height == 68984

# 1. Bestsellers of the last week before the cut (same as Lessons 42-43)
top12 = (
    tx.filter(pl.col("sale_date").is_between(pl.date(2020, 9, 9), pl.date(2020, 9, 15)))
    .group_by("article_id").agg(pl.len().alias("n"))
    .sort("n", descending=True).head(12)
    .collect()["article_id"].to_list()
)

# 2. Each customer's own items from the last 4 weeks (saved by Lesson 43)
hist = pl.read_parquet("data/clean/reco_again.parquet")
assert hist.height == 235277
again = dict(zip(hist["customer_id"], hist["again"].to_list()))

# 3. Baskets = one customer on one day; count how often two different items share a basket
recent = (
    tx.filter(pl.col("sale_date").is_between(pl.date(2020, 8, 19), pl.date(2020, 9, 15)))
    .select(["customer_id", "sale_date", "article_id"])
    .unique()
    .collect()
)
print(f"Basket lines (unique item per customer-day): {recent.height:,}")
print(f"Baskets: {recent.select(['customer_id', 'sale_date']).n_unique():,}")

pairs = (
    recent.join(recent, on=["customer_id", "sale_date"], suffix="_partner")
    .filter(pl.col("article_id") != pl.col("article_id_partner"))
    .group_by(["article_id", "article_id_partner"]).agg(pl.len().alias("n_baskets"))
)
print(f"Distinct item pairs: {pairs.height:,}")

partners = (
    pairs.filter(pl.col("n_baskets") >= 2)
    .sort(["article_id", "n_baskets", "article_id_partner"], descending=[False, True, False])
    .group_by("article_id", maintain_order=True).head(3)
)
print(f"Items with at least one partner (seen together 2+ times): {partners['article_id'].n_unique():,}")
arts = pl.read_parquet("data/parquet/articles.parquet").select(["article_id", "prod_name"])
example = top12[0]
print(f"\nExample - top-3 partners of the #1 bestseller {example}:")
print(
    partners.filter(pl.col("article_id") == example)
    .join(arts, on="article_id").join(arts, left_on="article_id_partner", right_on="article_id", suffix="_partner")
    .select(["prod_name", "article_id_partner", "prod_name_partner", "n_baskets"])
    .sort("n_baskets", descending=True)
)
partner_of = (
    partners.group_by("article_id", maintain_order=True)
    .agg(pl.col("article_id_partner").alias("p"))
)
partner_of = dict(zip(partner_of["article_id"], partner_of["p"].to_list()))


# 4. Fill 12 slots: own items -> their partners -> bestsellers
def recommend(c, use_again=True, use_pairs=True):
    own = list(again.get(c, []))
    picks = list(own) if use_again else []
    if use_pairs:
        for a in own:
            for p in partner_of.get(a, []):
                if len(picks) < 12 and p not in picks:
                    picks.append(p)
    for a in top12:
        if len(picks) >= 12:
            break
        if a not in picks:
            picks.append(a)
    return picks[:12]


def hit_rate(**kw):
    hits = 0
    for c, bought in zip(test["customer_id"], test["bought"].to_list()):
        if set(bought) & set(recommend(c, **kw)):
            hits += 1
    return hits / test.height


base = hit_rate(use_pairs=False)
both = hit_rate()
print(f"\nPopular only:                 {hit_rate(use_again=False, use_pairs=False):.2%}")
print(f"Buy-again + popular (L43):    {base:.2%}")
print(f"Pairs + popular (no again):   {hit_rate(use_again=False):.2%}")
print(f"Buy-again + pairs + popular:  {both:.2%}")
print(f"Change vs Lesson 43: {both - base:+.2%} points ({both / base - 1:+.1%})")
assert both > 0.1065, "must beat the Lesson 43 baseline"

# 5. Who gains? customers with history vs without
has_hist = test["customer_id"].is_in(list(again.keys()))
print(f"\nTest buyers with 4-week history: {has_hist.sum():,} of {test.height:,}")
sub = test.filter(has_hist)
for label, kw in [("L43 buy-again + popular", {"use_pairs": False}), ("L44 + pairs", {})]:
    h = sum(bool(set(b) & set(recommend(c, **kw))) for c, b in zip(sub["customer_id"], sub["bought"].to_list()))
    print(f"  Hit rate among them, {label}: {h / sub.height:.2%}")
avg_own = np.mean([min(len(again[c]), 12) for c in sub["customer_id"]])
print(f"  Avg own items per such customer: {avg_own:.1f} (so about {12 - avg_own:.1f} slots left for partners/bestsellers)")
partners.write_parquet("data/clean/reco_pairs.parquet")
