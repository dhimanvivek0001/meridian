# Compare LightGBM with logistic regression on the same churn data (same time split)
import polars as pl
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score, roc_auc_score

train = pl.read_parquet("data/clean/churn_train.parquet")
test = pl.read_parquet("data/clean/churn_test.parquet")
names = ["days_since", "visits", "spend", "items", "online_share"]
X_train, y_train = train.select(names).to_numpy(), train["churned"].to_numpy()
X_test, y_test = test.select(names).to_numpy(), test["churned"].to_numpy()

lgb = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, random_state=42, verbose=-1)
lgb.fit(X_train, y_train)
risk2 = lgb.predict_proba(X_test)[:, 1]

accuracy = accuracy_score(y_test, (risk2 >= 0.5).astype(int)) * 100
auc = roc_auc_score(y_test, risk2)
print(f"LightGBM accuracy {accuracy:.1f}%  AUC {auc:.3f}  (logistic regression: 75.3%, 0.792)")