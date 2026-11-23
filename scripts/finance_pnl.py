# Lesson 51: a simple P&L for Meridian + the money impact of earlier lessons, in one currency, with stated assumptions
import numpy as np
import polars as pl

SEED = 51
np.random.seed(SEED)

# ---- Assumptions (prices are disguised, so EUR figures are illustrative; every number is also shown in price units) ----
A = {
    "EUR_PER_UNIT": 590.0,       # 1 price_index unit in EUR: makes the median item (0.0254) cost ~EUR 15 (a guess)
    "GROSS_MARGIN": 0.50,        # cost of goods = 50% of the selling price (same as L36/L41)
    "MKT_EUR_DAY": 47_962.0,     # marketing budget per day (L33's simulated media plan)
    "SAVE_RATE": 0.20,           # vouchers keep 20% of would-be leavers (L17, confirmed 17.7-20.9% by the L24-25 A/B test)
    "VOUCHER_COST": 0.02,        # one voucher, price units (L17)
    "CAMPAIGNS_PER_YEAR": 1,     # churn campaign: value = 12 months of spend, so one per year
    "CLEARANCES_PER_YEAR": 2,    # end-of-season clearance (Jan + Jul)
    "NEWSVENDOR_PERIODS": 52 / 8,  # L41 measured 8 weeks
}
print("Assumptions:")
for k, v in A.items():
    print(f"  {k:20s} {v:,.2f}")
eur = lambda units: units * A["EUR_PER_UNIT"]

# ---- 1. Weekly P&L (full Monday-Sunday weeks only) ----
tx = pl.scan_parquet("data/clean/transactions.parquet")
assert tx.select(pl.len()).collect().item() == 31_788_324
weekly = (
    tx.with_columns(pl.col("sale_date").dt.truncate("1w").alias("week"))
    .group_by("week").agg(
        pl.col("sale_date").n_unique().alias("days"),
        pl.len().alias("items"),
        pl.col("price_index").sum().alias("revenue"),
        pl.col("price_index").filter(pl.col("sales_channel") == "online").sum().alias("online_rev"),
    )
    .filter(pl.col("days") == 7).sort("week").collect()
)
assert weekly.height == 104
weekly = weekly.with_columns(
    (pl.col("revenue") * (1 - A["GROSS_MARGIN"])).alias("cogs"),
    (pl.col("revenue") * A["GROSS_MARGIN"]).alias("gross_margin"),
    pl.lit(7 * A["MKT_EUR_DAY"] / A["EUR_PER_UNIT"]).alias("marketing"),
    pl.int_range(pl.len()).truediv(52).floor().cast(pl.Int32).add(1).alias("year"),
).with_columns((pl.col("gross_margin") - pl.col("marketing")).alias("contribution"))

print("\nWeekly P&L, last 6 weeks (EUR thousands):")
print("  week          items   revenue    COGS  gross margin  marketing  contribution")
for r in weekly.tail(6).iter_rows(named=True):
    print(f"  {r['week']}  {r['items']:>8,}  {eur(r['revenue']) / 1e3:8,.0f}  {eur(r['cogs']) / 1e3:6,.0f}"
          f"  {eur(r['gross_margin']) / 1e3:12,.0f}  {eur(r['marketing']) / 1e3:9,.0f}  {eur(r['contribution']) / 1e3:12,.0f}")

yr = weekly.group_by("year").agg(
    pl.col("items").sum(), pl.col("revenue").sum(), pl.col("online_rev").sum(), pl.col("gross_margin").sum(),
    pl.col("marketing").sum(), pl.col("contribution").sum(), pl.col("week").min().alias("start"),
).sort("year")
y1, y2 = yr.row(0, named=True), yr.row(1, named=True)
print("\nAnnual P&L (52 weeks each)           Year 1      Year 2    change")
print(f"  {'starts':28s} {str(y1['start']):>11s} {str(y2['start']):>11s}")
for label, k, money in [("Items sold", "items", False), ("Revenue (EUR m)", "revenue", True), ("Gross margin (EUR m)", "gross_margin", True),
                        ("Marketing (EUR m)", "marketing", True), ("Contribution (EUR m)", "contribution", True)]:
    a, b = (eur(y1[k]) / 1e6, eur(y2[k]) / 1e6) if money else (y1[k], y2[k])
    fmt = "{:11,.1f}" if money else "{:11,.0f}"
    print(f"  {label:28s} {fmt.format(a)} {fmt.format(b)}   {b / a - 1:+6.1%}")
print(f"  {'Revenue per item (EUR)':28s} {eur(y1['revenue'] / y1['items']):11,.2f} {eur(y2['revenue'] / y2['items']):11,.2f}"
      f"   {(y2['revenue'] / y2['items']) / (y1['revenue'] / y1['items']) - 1:+6.1%}")
print(f"  {'Online share of revenue':28s} {y1['online_rev'] / y1['revenue']:11.1%} {y2['online_rev'] / y2['revenue']:11.1%}")
print(f"  {'Marketing / revenue':28s} {y1['marketing'] / y1['revenue']:11.1%} {y2['marketing'] / y2['revenue']:11.1%}")
lo, hi = weekly.sort("revenue").row(0, named=True), weekly.sort("revenue").row(-1, named=True)
print(f"  Weakest week {lo['week']}: EUR {eur(lo['revenue']) / 1e6:.2f}m | strongest {hi['week']}: EUR {eur(hi['revenue']) / 1e6:.2f}m")
GM2 = y2["gross_margin"]
avg_price = y2["revenue"] / y2["items"]

# ---- 2. Money impact of earlier lessons, all converted to annual price units ----
impact = []

# L17 churn vouchers. L17 valued a saved customer at their full 12-month SPEND (revenue). Profit needs MARGIN.
scores = pl.read_parquet("data/clean/churn_scores.parquet")
test = pl.read_parquet("data/clean/churn_test.parquet").select("customer_id", "spend")
cust = scores.join(test, on="customer_id")
assert cust.height == 984_525
for label, value in [("revenue (as in L17)", pl.col("spend")), ("margin (corrected)", pl.col("spend") * A["GROSS_MARGIN"])]:
    p = cust.with_columns((pl.col("risk") * A["SAVE_RATE"] * value - A["VOUCHER_COST"]).alias("p")).filter(pl.col("p") > 0)
    print(f"\nL17 vouchers valued on {label}: {p.height:,} vouchers, expected gain {p['p'].sum():,.0f} units")
    if label.startswith("margin"):
        impact.append(("L17 churn vouchers (profit > 0 only)", p["p"].sum() * A["CAMPAIGNS_PER_YEAR"],
                       f"{p.height:,} vouchers; save rate 20% (A/B confirmed); 1 campaign/yr"))

# L37 clearance: L37 money is in "full price = 1" per item; multiply by each item's full price (highest Aug-2020 price)
plan = pl.read_parquet("data/clean/clearance_plan.parquet")
assert plan.height == 9_320
full = (tx.filter(pl.col("sale_date").is_between(pl.date(2020, 8, 1), pl.date(2020, 8, 31)))
        .group_by("article_id").agg(pl.col("price_index").max().alias("full_price")).collect())
plan = plan.join(full, on="article_id", how="left")
assert plan["full_price"].null_count() == 0
gain37 = ((plan["money"] - plan["money_no_disc"]) * plan["full_price"]).sum()
print(f"L37 smart markdowns vs no discount: {gain37:,.1f} units per clearance (avg full price {plan['full_price'].mean():.4f})")
impact.append(("L37 per-item clearance markdowns", gain37 * A["CLEARANCES_PER_YEAR"],
               "9,320 items, simulated stock; vs no discount; 2 clearances/yr"))
# L37 reported totals: no discount 1,657,559 vs flat 50% off 1,387,018 (full-price units)
impact.append(("  (avoided) flat 50%-off sale", (1_387_018 - 1_657_559) * plan["full_price"].mean() * A["CLEARANCES_PER_YEAR"],
               "what a blanket sale would cost vs no discount"))

# L41 newsvendor: profit in "price = 1 per unit"; convert with the Year-2 average revenue per item
l41 = {"perfect": 1_096_230, "last_year": 926_044, "newsvendor": 923_011, "high90": 318_018}
k = avg_price * A["NEWSVENDOR_PERIODS"]
impact.append(("L41 newsvendor vs order-last-year", (l41["newsvendor"] - l41["last_year"]) * k, "a tie: no gain"))
impact.append(("L41 avoid 'never run out' (90th pct)", (l41["newsvendor"] - l41["high90"]) * k, "loss avoided vs ordering the high case"))
impact.append(("L41 perfect forecast (upper bound)", (l41["perfect"] - l41["newsvendor"]) * k, "price of uncertainty, not achievable"))

# L33 MMM re-split: budget-neutral, so the gain is the extra margin on extra items
true_items, promised_items = 119, 3_097
impact.append(("L33 MMM budget re-split (true effect)", true_items * 365 * avg_price * A["GROSS_MARGIN"], "same spend; +119 items/day"))
impact.append(("  (what the MMM promised)", promised_items * 365 * avg_price * A["GROSS_MARGIN"], "26x over-promised (optimizer's curse)"))

# Sanity check: L41's "perfect" profit is company-wide units x margin, so per year it should be close to the P&L's gross margin
print(f"\nCheck: L41 perfect-forecast profit per year = {l41['perfect'] * k / GM2:.0%} of Year-2 gross margin (should be near 100%)")

print(f"\nMoney impact per year (Year-2 gross margin = EUR {eur(GM2) / 1e6:,.1f}m; avg revenue per item {avg_price:.4f} units = EUR {eur(avg_price):.2f})")
print(f"  {'Lesson / decision':40s} {'units':>9s} {'EUR m':>7s} {'% of GM':>8s}  note")
for name, u, note in impact:
    print(f"  {name:40s} {u:9,.0f} {eur(u) / 1e6:7.2f} {u / GM2:8.2%}  {note}")
# Only count gains vs what the business does TODAY (no vouchers, no clearance discount, order = last year, current media split).
# Strawmen ("never run out", flat 50% sale) and upper bounds are context, not gains.
counted = ["L17 churn", "L37 per-item", "L41 newsvendor vs", "L33 MMM budget"]
real = [u for n, u, _ in impact if any(n.startswith(c) for c in counted)]
assert len(real) == 4
print(f"  {'TOTAL vs today (4 counted lines)':40s} {sum(real):9,.0f} {eur(sum(real)) / 1e6:7.2f} {sum(real) / GM2:8.2%}")

weekly.with_columns(pl.col("revenue").mul(A["EUR_PER_UNIT"]).alias("revenue_eur")).write_parquet("data/clean/pnl_weekly.parquet")
