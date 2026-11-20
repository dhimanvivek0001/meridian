# Churn model: logistic regression, trained on cutoff 2 Jun 2020, tested on cutoff 28 Jul 2020
import polars as pl
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

train = pl.read_parquet("data/clean/churn_train.parquet")
test = pl.read_parquet("data/clean/churn_test.parquet")

# 1. Clues (big ones shrunk with log) and answers
names = ["days_since", "visits", "spend", "items", "online_share"]
clues = [pl.col("days_since").log1p(), pl.col("visits").log1p(), pl.col("spend").log1p(),
         pl.col("items").log1p(), pl.col("online_share")]
X_train, y_train = train.select(clues).to_numpy(), train["churned"].to_numpy()
X_test, y_test = test.select(clues).to_numpy(), test["churned"].to_numpy()

# 2. Learn on train (scaler learns normal/wiggle from train only)
model = make_pipeline(StandardScaler(), LogisticRegression())
model.fit(X_train, y_train)

# 3. Check on the later date
risk = model.predict_proba(X_test)[:, 1]
baseline = y_test.mean() * 100
accuracy = accuracy_score(y_test, (risk >= 0.5).astype(int)) * 100
auc = roc_auc_score(y_test, risk)
print(f"baseline {baseline:.1f}%  accuracy {accuracy:.1f}%  AUC {auc:.3f}")
assert accuracy > baseline, "Model does not beat the lazy guess"

# 4. What it learned
weights = model.named_steps["logisticregression"].coef_[0]
for n, w in zip(names, weights):
    print(f"  {n:13s} {w:+.2f}")

# 5. Risk bands: does real churn climb with risk?
scored = test.with_columns(pl.Series("risk", risk))
scored = scored.with_columns(
    pl.col("risk").qcut(10, labels=[f"{i:02d}" for i in range(1, 11)]).alias("risk_band")
)
bands = (
    scored.group_by("risk_band")
    .agg(pl.len().alias("customers"), (pl.col("churned").mean() * 100).round(1).alias("churn_pct"))
    .sort("risk_band")
)
print(bands)
bands.write_csv("reports/churn_risk_bands.csv")
scored.select("customer_id", "risk", "risk_band", "churned").write_parquet("data/clean/churn_scores.parquet")
print("Saved reports/churn_risk_bands.csv and data/clean/churn_scores.parquet")