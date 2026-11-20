# Explain one customer's churn risk: which clues pushed it up or down (SHAP values from LightGBM)
import polars as pl
from lightgbm import LGBMClassifier

train = pl.read_parquet("data/clean/churn_train_v2.parquet")
test = pl.read_parquet("data/clean/churn_test_v2.parquet")
names = ["days_since", "visits", "spend", "items", "online_share",
         "visits_4w", "visits_prev12w", "avg_gap", "overdue",
         "age", "FN", "club_active", "news_regular"]

lgb = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, random_state=42, verbose=-1)
lgb.fit(train.select(names).to_numpy(), train["churned"].to_numpy())

X_test = test.select(names).to_numpy()
test = test.with_columns(pl.Series("risk", lgb.predict_proba(X_test)[:, 1])).with_row_index("row")

# 1. Pick a valuable customer who is at risk
top_spend = test["spend"].quantile(0.9)
pick = test.filter((pl.col("spend") > top_spend) & pl.col("risk").is_between(0.6, 0.8)).head(1)
i = pick["row"][0]
print("Customer:", pick["customer_id"][0][:12], "...  risk", round(pick["risk"][0], 2),
      "  really churned:", pick["churned"][0])

# 2. Split their risk into pushes, one per clue
pushes = lgb.predict(X_test[i:i + 1], pred_contrib=True)[0]
print("\nclue            value      push")
for n, p in sorted(zip(names, pushes[:-1]), key=lambda x: -abs(x[1])):
    print(f"{n:15s} {test[n][i]:>8.2f}   {p:+.2f}  {'UP' if p > 0 else 'down'}")

# 3. Plain-English reasons: the 3 biggest UP pushes
ups = [n for n, p in sorted(zip(names, pushes[:-1]), key=lambda x: -x[1]) if p > 0][:3]
print("\nAt risk mainly because of:", ", ".join(ups))