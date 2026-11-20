# Churn model v2: same time split, 13 clues instead of 5. Compare with v1 (AUC 0.792 / 0.793)
import polars as pl
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score

train = pl.read_parquet("data/clean/churn_train_v2.parquet")
test = pl.read_parquet("data/clean/churn_test_v2.parquet")

names = ["days_since", "visits", "spend", "items", "online_share",
         "visits_4w", "visits_prev12w", "avg_gap", "overdue",
         "age", "FN", "club_active", "news_regular"]
logged = ["days_since", "visits", "spend", "items", "visits_4w", "visits_prev12w", "avg_gap", "overdue"]
clues = [pl.col(n).log1p() if n in logged else pl.col(n) for n in names]

y_train, y_test = train["churned"].to_numpy(), test["churned"].to_numpy()

# 1. Logistic regression (shrink big clues, then scale)
X_train, X_test = train.select(clues).to_numpy(), test.select(clues).to_numpy()
logreg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
logreg.fit(X_train, y_train)
auc_lr = roc_auc_score(y_test, logreg.predict_proba(X_test)[:, 1])

# 2. LightGBM (raw clues, trees don't need shrinking)
R_train, R_test = train.select(names).to_numpy(), test.select(names).to_numpy()
lgb = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, random_state=42, verbose=-1)
lgb.fit(R_train, y_train)
auc_lgb = roc_auc_score(y_test, lgb.predict_proba(R_test)[:, 1])

print(f"Logistic regression  v1 0.792 -> v2 {auc_lr:.3f}")
print(f"LightGBM             v1 0.793 -> v2 {auc_lgb:.3f}")

# 3. Which clues did LightGBM rely on most?
gain = lgb.booster_.feature_importance("gain")
share = gain / gain.sum() * 100
for n, s in sorted(zip(names, share), key=lambda x: -x[1]):
    print(f"  {n:15s} {s:5.1f}%")