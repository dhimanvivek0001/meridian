# Lesson 43: "buy again" recommender - customer's own recent items first, bestsellers fill the gaps
import polars as pl

tx = pl.scan_parquet("data/clean/transactions.parquet")
test = pl.read_parquet("data/clean/reco_test.parquet")
top12 = (
    tx.filter(pl.col("sale_date").is_between(pl.date(2020, 9, 9), pl.date(2020, 9, 15)))
    .group_by("article_id").agg(pl.len().alias("n"))
    .sort("n", descending=True).head(12)
    .collect()["article_id"].to_list()
)
hist = (
    tx.filter(pl.col("sale_date").is_between(pl.date(2020, 8, 19), pl.date(2020, 9, 15)))
    .group_by(["customer_id", "article_id"])
    .agg(pl.len().alias("n"), pl.col("sale_date").max().alias("last"))
    .sort(["customer_id", "n", "last"], descending=[False, True, True])
    .group_by("customer_id", maintain_order=True).head(12)
    .group_by("customer_id").agg(pl.col("article_id").alias("again"))
    .collect()
)
again = dict(zip(hist["customer_id"], hist["again"].to_list()))
print(f"Customers with a purchase in the last 4 weeks: {len(again):,}")


def recommend(c, use_again=True):
    picks = list(again.get(c, [])) if use_again else []
    for a in top12:
        if len(picks) >= 12:
            break
        if a not in picks:
            picks.append(a)
    return picks


def hit_rate(use_again, only_again=False):
    hits = 0
    for c, bought in zip(test["customer_id"], test["bought"].to_list()):
        picks = list(again.get(c, [])) if only_again else recommend(c, use_again)
        if set(bought) & set(picks):
            hits += 1
    return hits / test.height


print(f"Popular only:          {hit_rate(False):.2%}")
print(f"Buy-again only:        {hit_rate(True, only_again=True):.2%}")
print(f"Buy-again + popular:   {hit_rate(True):.2%}")
hist.write_parquet("data/clean/reco_again.parquet")