# Churn targeting: who is worth a voucher? expected profit = risk x save rate x value - cost
import polars as pl

# Assumptions (no real campaign data yet; test the save rate with an A/B test later)
SAVE_RATE = 0.20   # share of would-be leavers a voucher keeps
COST = 0.02        # cost of one voucher (index units, ~10% of a typical basket)

scores = pl.read_parquet("data/clean/churn_scores.parquet")
test = pl.read_parquet("data/clean/churn_test.parquet")
df = scores.join(test.select("customer_id", "spend"), on="customer_id")
assert df.height == scores.height, "Some customers lost in the join"

df = df.with_columns((pl.col("risk") * SAVE_RATE * pl.col("spend") - COST).alias("exp_profit"))

def total(name, chosen):
    return {"strategy": name, "contacted": chosen.height, "exp_profit": round(chosen["exp_profit"].sum(), 1)}

results = pl.DataFrame([
    total("Contact everyone", df),
    total("Riskiest 10% only", df.filter(pl.col("risk_band") == "10")),
    total("Only if profit > 0", df.filter(pl.col("exp_profit") > 0)),
])
print(results)
results.write_csv("reports/churn_targeting.csv")
df.filter(pl.col("exp_profit") > 0).select("customer_id", "risk", "spend", "exp_profit") \
  .write_parquet("data/clean/voucher_list.parquet")
print("Saved reports/churn_targeting.csv and data/clean/voucher_list.parquet")