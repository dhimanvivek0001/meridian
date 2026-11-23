# Lesson 53: transaction-level anomalies - odd prices, bulk buying, huge baskets (rules) vs Isolation Forest on customers
import numpy as np
import polars as pl
from sklearn.ensemble import IsolationForest

SEED = 53
np.random.seed(SEED)
LOW, HIGH = 0.3, 3.0      # price flag: below 30% or above 3x what others paid for the same article, week and channel
MIN_REF = 10              # ...and only if at least 10 sales give a reliable "what others paid"
BULK = 10                 # bulk: 10+ units of the SAME article by one customer on one day
BASKET = 60               # huge basket: 60+ items by one customer on one day (top ~0.01% of shopping days)

tx = pl.scan_parquet("data/clean/transactions.parquet").with_columns(pl.col("sale_date").dt.truncate("1w").alias("week"))
n_tx = tx.select(pl.len()).collect().item()
assert n_tx == 31_788_324

# 1. Price outliers: compare each line to the median price of the same article, same week, same channel
ref = tx.group_by(["article_id", "week", "sales_channel"]).agg(pl.col("price_index").median().alias("ref"), pl.len().alias("n_ref"))
priced = tx.join(ref, on=["article_id", "week", "sales_channel"]).with_columns((pl.col("price_index") / pl.col("ref")).alias("ratio"))
pf = priced.filter((pl.col("n_ref") >= MIN_REF) & ((pl.col("ratio") < LOW) | (pl.col("ratio") > HIGH))).collect()
checked = priced.filter(pl.col("n_ref") >= MIN_REF).select(pl.len()).collect().item()
print(f"Price outliers: {pf.height:,} of {checked:,} checkable lines ({pf.height / checked:.3%}); "
      f"low {(pf['ratio'] < LOW).sum():,} / high {(pf['ratio'] > HIGH).sum():,}")

# Evidence: did OTHER customers pay the same price for that article on the same day and channel? (systematic vs isolated)
same = (tx.with_columns(pl.col("price_index").round(6).alias("p6"))
        .group_by(["article_id", "sale_date", "sales_channel", "p6"]).agg(pl.len().alias("same_price_lines")))
pf = (pf.with_columns(pl.col("price_index").round(6).alias("p6"))
      .join(same.collect(), on=["article_id", "sale_date", "sales_channel", "p6"], how="left")
      .with_columns((pl.col("same_price_lines") - 1).alias("others_same_price")))
print(f"  ...where 3+ other lines paid the identical price that day (systematic, e.g. a price change mid-week): "
      f"{(pf['others_same_price'] >= 3).mean():.1%}")
print(f"  ...exactly 80% off (ratio 0.195-0.205): {pf['ratio'].is_between(0.195, 0.205).sum():,} lines, "
      f"{pf.filter(pl.col('ratio').is_between(0.195, 0.205))['customer_id'].n_unique():,} customers")
top80 = (pf.filter(pl.col("ratio").is_between(0.195, 0.205)).group_by("customer_id").agg(pl.len().alias("n"))
         .sort("n", descending=True))
print(f"  ...80%-off lines from the top 10 customers: {top80.head(10)['n'].sum() / top80['n'].sum():.0%}")

# 2. Bulk buying: many units of one article by one customer on one day
q = tx.group_by(["customer_id", "sale_date", "article_id"]).agg(pl.len().alias("units"), pl.col("price_index").mean().alias("price"),
                                                                 pl.col("sales_channel").first())
bulk = q.filter(pl.col("units") >= BULK).collect()
print(f"\nBulk lines (>= {BULK} units of one article, one customer, one day): {bulk.height:,} by {bulk['customer_id'].n_unique():,} customers; "
      f"max {bulk['units'].max()} units")
rep = bulk.group_by("customer_id").agg(pl.col("sale_date").n_unique().alias("bulk_days")).filter(pl.col("bulk_days") >= 3)
print(f"  customers with bulk buys on 3+ different days (reseller-like): {rep.height:,}")

# 3. Huge baskets
basket = tx.group_by(["customer_id", "sale_date"]).agg(pl.len().alias("items"), pl.col("article_id").n_unique().alias("distinct"),
                                                       pl.col("price_index").sum().alias("spend"), pl.col("sales_channel").first())
big = basket.filter(pl.col("items") >= BASKET).collect()
print(f"Huge baskets (>= {BASKET} items in a day): {big.height:,} by {big['customer_id'].n_unique():,} customers")

# 4. Model: Isolation Forest on one row per customer (8 behaviour features), flag the 500 most isolated customers
cust = (
    q.group_by("customer_id").agg(
        pl.col("units").sum().alias("items"), pl.col("sale_date").n_unique().alias("days"),
        pl.col("units").max().alias("max_same_article"), (pl.col("units") >= 3).mean().alias("multi_share"),
        (pl.col("sales_channel") == "online").mean().alias("online_share"),
    )
    .join(basket.group_by("customer_id").agg(pl.col("items").max().alias("max_basket")), on="customer_id")
    .join(priced.group_by("customer_id").agg(pl.col("ratio").median().alias("med_ratio"),
                                            (pl.col("ratio") < 0.5).mean().alias("cheap_share")), on="customer_id")
    .collect().sort("customer_id")
)
assert cust.height == 1_362_281
feats = ["items", "days", "max_same_article", "multi_share", "online_share", "max_basket", "med_ratio", "cheap_share"]
X = cust.select([pl.col(f).cast(pl.Float64) for f in feats]).to_numpy()
X[:, [0, 1, 2, 5]] = np.log1p(X[:, [0, 1, 2, 5]])  # counts are very skewed: log them
iso = IsolationForest(n_estimators=300, random_state=SEED).fit(X)
cust = cust.with_columns(pl.Series("iso", -iso.score_samples(X)))
iso_top = cust.sort(["iso", "customer_id"], descending=[True, False]).head(500)
rule_custs = set(bulk["customer_id"]) | set(big["customer_id"])
price_custs = set(pf["customer_id"])
print(f"\nIsolation Forest top 500 customers: {len(set(iso_top['customer_id']) & rule_custs)} also caught by bulk/basket rules, "
      f"{len(set(iso_top['customer_id']) & price_custs)} by the price rule")
print("  typical flagged vs all customers (median):")
for f in feats:
    print(f"    {f:18s} {iso_top[f].median():9.2f}  vs  {cust[f].median():7.2f}")

# Extra evidence for the reviewer: product name/type, the article's usual full price, customer's shopping days
arts = pl.read_parquet("data/parquet/articles.parquet").select("article_id", "prod_name", "product_type_name")
full = (tx.group_by("article_id").agg(pl.col("price_index").quantile(0.9).alias("p90"), pl.col("price_index").quantile(0.1).alias("p10"))
        .collect())
cdays = cust.select("customer_id", pl.col("days").alias("cust_days"), pl.col("items").alias("cust_items"))
pf = pf.join(full, on="article_id", how="left").join(arts, on="article_id", how="left")
bulk = bulk.join(arts, on="article_id", how="left").join(cdays, on="customer_id", how="left").join(rep, on="customer_id", how="left")
big = big.join(cdays, on="customer_id", how="left")

# 5. Samples for a HAND check of precision: 12 random flags per detector, with the evidence a reviewer needs.
#    Sorted on a unique key first: joins don't keep row order, and sample(seed) needs the same input order to repeat.
cid = {c: f"C{i:03d}" for i, c in enumerate(sorted(set(pf["customer_id"]) | rule_custs | set(iso_top["customer_id"])))}  # short ids
print("\n=== Sample A: price outliers (ratio = price / median others paid that week) ===")
for r in pf.sort(['sale_date', 'customer_id', 'article_id', 'price_index']).sample(12, seed=SEED).sort("ratio").iter_rows(named=True):
    print(f"  {r['sale_date']} {r['sales_channel']:6s} art {r['article_id']} ratio {r['ratio']:5.2f}  ref n={r['n_ref']:4d}  "
          f"others same price: {r['others_same_price']}  price vs article's usual range (p10-p90): {r['price_index'] / r['p10']:.2f}x p10, {r['price_index'] / r['p90']:.2f}x p90  [{r['product_type_name']}] {r['prod_name']}")
print("\n=== Sample B: bulk lines ===")
for r in bulk.sort(['sale_date', 'customer_id', 'article_id']).sample(12, seed=SEED).sort("units").iter_rows(named=True):
    print(f"  {r['sale_date']} {r['sales_channel']:6s} {cid[r['customer_id']]} art {r['article_id']} units {r['units']:3d}  price {r['price']:.4f}  [{r['product_type_name']}] {r['prod_name']}  cust days {r['cust_days']} bulk days {r['bulk_days'] or '<3'}")
print("\n=== Sample C: huge baskets ===")
for r in big.sort(['sale_date', 'customer_id']).sample(12, seed=SEED).sort("items").iter_rows(named=True):
    print(f"  {r['sale_date']} {r['sales_channel']:6s} {cid[r['customer_id']]} items {r['items']:3d}  distinct articles {r['distinct']:3d}  spend {r['spend']:.3f}  cust days {r['cust_days']} cust items {r['cust_items']}")
print("\n=== Sample D: Isolation Forest customers (out of top 500) ===")
for r in iso_top.sample(12, seed=SEED).sort("iso", descending=True).iter_rows(named=True):
    print(f"  {cid[r['customer_id']]} items {r['items']:5d} days {r['days']:3d} max_same {r['max_same_article']:3d} multi {r['multi_share']:.2f} "
          f"online {r['online_share']:.2f} max_basket {r['max_basket']:3d} med_ratio {r['med_ratio']:.2f} cheap {r['cheap_share']:.2f}")

cust.select(["customer_id", "iso"] + feats).write_parquet("data/clean/customer_anomaly.parquet")
