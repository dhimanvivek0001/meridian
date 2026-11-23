# Lesson 52: anomaly detection on daily sales by channel x product group - rolling z-score vs seasonal residual vs Isolation Forest
from datetime import timedelta

import numpy as np
import polars as pl
from sklearn.ensemble import IsolationForest

SEED = 52
rng = np.random.default_rng(SEED)
BUDGET = 20  # each method flags its 20 most unusual days (~3% of days), so methods are compared fairly

tx = pl.scan_parquet("data/clean/transactions.parquet")
arts = pl.scan_parquet("data/parquet/articles.parquet").select("article_id", "product_group_name", "prod_name")
TOP = ["Garment Upper body", "Garment Lower body", "Garment Full body", "Swimwear", "Underwear", "Accessories"]

# 1. Daily units for 2 channels x 7 product groups = 14 series
daily = (
    tx.join(arts, on="article_id")
    .with_columns(pl.when(pl.col("product_group_name").is_in(TOP)).then(pl.col("product_group_name")).otherwise(pl.lit("Other")).alias("grp"))
    .group_by(["sale_date", "sales_channel", "grp"]).agg(pl.len().alias("units"))
    .collect()
)
days = pl.date_range(daily["sale_date"].min(), daily["sale_date"].max(), "1d", eager=True).to_list()
series = sorted(daily.select(["sales_channel", "grp"]).unique().iter_rows())
assert len(days) == 734 and len(series) == 14
D, S = len(days), len(series)
pos = {d: i for i, d in enumerate(days)}
sid = {s: k for k, s in enumerate(series)}
Y = np.zeros((D, S))
for d, ch, g, n in daily.iter_rows():
    Y[pos[d], sid[(ch, g)]] = n
L = np.log1p(Y)  # log scale: a doubling is the same size for a big and a small series
wday = np.array([d.weekday() for d in days])
print(f"{D} days x {S} series (channel x product group); total units {Y.sum():,.0f}")


def roll(x, w, fn, center):
    """Rolling statistic down each column (pandas-free): trailing window (past only) or centred."""
    out = np.full_like(x, np.nan)
    for i in range(len(x)):
        lo, hi = (i - w // 2, i + w // 2 + 1) if center else (i - w, i)
        if lo >= 0 and hi <= len(x):
            out[i] = fn(x[lo:hi], axis=0)
    return out


# Method A - rolling z-score: today vs the mean/std of the previous 28 days (what a simple dashboard alert does)
def z_rolling(L):
    m, s = roll(L, 28, np.mean, False), roll(L, 28, np.std, False)
    return (L - m) / np.maximum(s, 0.05)


# Method B - seasonal residual: remove a smooth level (centred 29-day median) AND the weekday pattern, then robust z
def z_seasonal(L):
    base = roll(L, 29, np.median, True)
    r = L - base
    for w in range(7):  # each series' typical weekday effect (Saturdays differ from Tuesdays)
        r[wday == w] -= np.nanmedian(r[wday == w], axis=0)
    mad = 1.4826 * np.nanmedian(np.abs(r - np.nanmedian(r, axis=0)), axis=0)  # robust spread: outliers can't inflate it
    return r / np.maximum(mad, 0.05)


# Method C - Isolation Forest on each day's 14 seasonal residuals: which days look unlike the others as a whole?
def iforest(L):
    z = np.nan_to_num(z_seasonal(L))
    f = IsolationForest(n_estimators=300, random_state=SEED).fit(z)
    return -f.score_samples(z)  # higher = more isolated = more unusual


def day_scores(L):
    za, zb = z_rolling(L), z_seasonal(L)
    ok = ~np.isnan(zb).any(1) & ~np.isnan(za).any(1)  # skip the edges where a window doesn't fit
    sc = {"Rolling z (28 days back)": np.abs(za).max(1), "Seasonal residual": np.abs(zb).max(1), "Isolation Forest": iforest(L)}
    return {k: np.where(ok, v, -np.inf) for k, v in sc.items()}, za, zb


def top(score, k=BUDGET):
    return set(np.argsort(-score)[:k])


# 2. Planted test: hide 25 fake anomalies (one series x2 or x0.5 on one day) and see who finds them.
# Fair budget: each method's alarm threshold is set so it flags the same share (1/2/5/10%) of the REAL data.
valid = np.arange(30, D - 30)
plant_days = rng.choice(valid, 25, replace=False)
plant_series = rng.integers(0, S, 25)
plant_mult = rng.choice([2.0, 0.5], 25)
Yp = Y.copy()
Yp[plant_days, plant_series] *= plant_mult
Lp = np.log1p(Yp)
print(f"\nPlanted test: 25 fake anomalies (one series doubled or halved on one day), same alert volume for every method")
BUDGETS = [0.01, 0.02, 0.05, 0.10]  # share of the real data each method is allowed to flag
print(f"  {'method':28s} {'level':11s}" + "".join(f"  top {q:>3.0%}" for q in BUDGETS))
for name, fn in [("Rolling z (28 days back)", z_rolling), ("Seasonal residual", z_seasonal)]:
    real, fake = np.abs(fn(L)), np.abs(fn(Lp))
    hits = [(np.nan_to_num(fake[plant_days, plant_series]) > np.nanquantile(real, 1 - q)).sum() for q in BUDGETS]
    print(f"  {name:28s} {'series-day':11s}" + "".join(f"  {h:4d}/25" for h in hits))
real, fake = iforest(L), iforest(Lp)
hits = [(fake[plant_days] > np.quantile(real, 1 - q)).sum() for q in BUDGETS]
print(f"  {'Isolation Forest':28s} {'whole day':11s}" + "".join(f"  {h:4d}/25" for h in hits))

sc, za, zb = day_scores(L)

# 3. Real flags: which days, and how much do the methods agree?
flags = {k: top(v) for k, v in sc.items()}
names = list(flags)
print("\nAgreement on real data (days flagged by both):")
for i in range(3):
    for j in range(i + 1, 3):
        print(f"  {names[i]:26s} & {names[j]:20s}: {len(flags[names[i]] & flags[names[j]]):2d} / {BUDGET}")

# 4. Explain each flagged day with evidence: price level (sale?), online share (stores shut?), launches, top product
tot = pl.DataFrame({"sale_date": pl.Series(days, dtype=pl.Date), "units": Y.sum(1), "online": Y[:, [k for k, s in enumerate(series) if s[0] == "online"]].sum(1)})
price = tx.group_by("sale_date").agg(pl.col("price_index").mean().alias("price")).collect()
first = tx.group_by("article_id").agg(pl.col("sale_date").min().alias("first_sale"))
launch = (tx.join(first, on="article_id").group_by("sale_date")
          .agg(((pl.col("sale_date") - pl.col("first_sale")).dt.total_days() <= 2).mean().alias("launch_share")).collect())
ctx = (tot.join(price, on="sale_date").join(launch, on="sale_date").sort("sale_date")
       .with_columns(
           (pl.col("online") / pl.col("units")).alias("on_share"),
           (pl.col("units") / pl.col("units").rolling_median(29, center=True)).alias("vs_usual"),
           (pl.col("price") / pl.col("price").rolling_median(29, center=True)).alias("price_vs_usual"),
           pl.col("launch_share").rolling_median(29, center=True).alias("launch_usual"),
           pl.col("sale_date").dt.weekday().alias("wd"),
       )
       # usual online share for the SAME weekday (Sundays are online-heavy every week): median of the 9 same-weekdays around it
       .with_columns(pl.col("on_share").rolling_median(9, center=True).over("wd").alias("on_usual")))
union = sorted(set().union(*flags.values()), key=lambda i: -sc["Seasonal residual"][i])
print(f"\nFlagged days (union of the 3 methods: {len(union)} days), sorted by seasonal-residual score. Methods: R=rolling z, S=seasonal, I=iForest")
print("  date        day  by   units  vs usual  price vs usual  online (usual)  launches (usual)  most unusual series (z)")
causes = {}
for i in map(int, union):
    r = ctx.row(i, named=True)
    by = "".join(c for c, n in zip("RSI", names) if i in flags[n])
    k = int(np.nanargmax(np.abs(zb[i])))
    if r["launch_share"] > max(0.04, 2.5 * r["launch_usual"]):
        cause = "LAUNCH"
    elif r["price_vs_usual"] < 0.90 and r["vs_usual"] > 1.3:
        cause = "SALE EVENT"
    elif abs(r["on_share"] - r["on_usual"]) > 0.15:
        cause = "CHANNEL SHIFT (stores shut / reopen / site issue)"
    else:
        cause = "?"
    causes[str(days[i])] = cause
    print(f"  {days[i]}  {days[i].strftime('%a')}  {by:3s} {r['units']:7,.0f}  {r['vs_usual']:7.2f}x  {r['price_vs_usual']:13.2f}x"
          f"   {r['on_share']:5.0%} ({r['on_usual']:4.0%})   {r['launch_share']:6.1%} ({r['launch_usual']:4.1%})  {series[k][0]} {series[k][1]} ({zb[i, k]:+.1f})  {cause}")

print("\nLikely cause (rule-based):", {c: list(causes.values()).count(c) for c in sorted(set(causes.values()))})
for n in names:
    ok = sum(causes[str(days[i])] != "?" for i in flags[n])
    print(f"  {n:28s} {ok:2d} / {BUDGET} flagged days have an explanation")

# 5. Drill-down into the biggest UNEXPLAINED spike: what did people buy, and how much per person?
spikes = [(ctx["vs_usual"][i], i) for i in map(int, union) if causes[str(days[i])] == "?" and ctx["vs_usual"][i] > 1.5]
_, i = max(spikes)
d0 = days[i]
per_cust = (tx.filter(pl.col("sale_date").is_between(d0 - timedelta(days=14), d0 + timedelta(days=14)))
            .group_by("sale_date").agg((pl.len() / pl.col("customer_id").n_unique()).alias("ipc"), pl.col("customer_id").n_unique().alias("buyers"))
            .sort("sale_date").collect())
day_row = per_cust.filter(pl.col("sale_date") == d0)
others = per_cust.filter(pl.col("sale_date") != d0)
print(f"\nBiggest unexplained spike {d0} ({ctx['vs_usual'][i]:.1f}x usual units):")
print(f"  buyers {day_row['buyers'][0]:,} vs median {others['buyers'].median():,.0f} on the 28 days around it; "
      f"items per buyer {day_row['ipc'][0]:.2f} vs {others['ipc'].median():.2f}")
prods = (tx.filter(pl.col("sale_date") == d0).join(arts, on="article_id").group_by("prod_name").agg(pl.len().alias("n"))
         .sort("n", descending=True).head(5).collect())
print("  top products:", ", ".join(f"{a} ({n:,})" for a, n in prods.iter_rows()))
ctx.write_parquet("data/clean/daily_context.parquet")
