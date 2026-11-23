# Databricks notebook source
# MAGIC %md
# MAGIC Lesson 56: weekly churn scoring task (runs after gold in the meridian_weekly job). Same steps as scripts/weekly_pipeline.py.

# COMMAND ----------

# MAGIC %pip install lightgbm==4.7.0 mlflow==3.18.0 -q

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./05_churn_features

# COMMAND ----------

import os

# Free Edition blocks direct writes to Unity Catalog's cloud storage; this sends model files through the Databricks Files API
os.environ["MLFLOW_USE_DATABRICKS_SDK_MODEL_ARTIFACTS_REPO_FOR_UC"] = "true"
import json
import mlflow
import numpy as np
from pyspark.sql import functions as F

dbutils.widgets.text("cutoff", "2020-09-23")    # the job can pass a date; default = day after the last sale
CUTOFF = dbutils.widgets.get("cutoff")
MODEL = "workspace.meridian.churn_model"
SAVE_RATE, MARGIN, VOUCHER_COST = 0.20, 0.50, 0.02

# 1. Hard data checks: stop the task (and the job turns red) if the data is broken
tx = spark.table("workspace.meridian.silver_transactions")
s = tx.agg(
    F.max("sale_date").alias("max_date"),
    sum(F.sum(F.col(c).isNull().cast("int")) for c in ["customer_id", "article_id", "sale_date", "price_index", "sales_channel"]).alias("nulls"),
    F.sum(((F.col("price_index") <= 0) | (F.col("price_index") >= 1)).cast("int")).alias("bad_price"),
).first()
checks = {
    "data is fresh": str(s.max_date) >= str(np.datetime64(CUTOFF) - np.timedelta64(1, "D")),
    "no nulls in key columns": s.nulls == 0,
    "prices between 0 and 1": s.bad_price == 0,
}
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
if not all(checks.values()):
    raise RuntimeError(f"STOPPED: data checks failed for cutoff {CUTOFF} - nothing scored")

# COMMAND ----------

# 2. Features (shared code) + 3. champion model from Unity Catalog
mlflow.set_registry_uri("databricks-uc")
feat = make_features(CUTOFF).toPandas().sort_values("customer_id").reset_index(drop=True)
model = mlflow.lightgbm.load_model(f"models:/{MODEL}@champion")
risk = model.predict_proba(feat[FEATURES].to_numpy())[:, 1]
print(f"{len(feat):,} customers scored with {MODEL}@champion, mean risk {risk.mean():.1%}")

# 4. Drift: PSI of each feature vs the training features
ref = spark.table("workspace.meridian.churn_train_features").toPandas()


def psi(r, c, bins=10):
    edges = np.unique(np.quantile(r, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    rp = np.clip(np.histogram(r, edges)[0] / len(r), 1e-4, None)
    cp = np.clip(np.histogram(c, edges)[0] / len(c), 1e-4, None)
    return float(((cp - rp) * np.log(cp / rp)).sum())


drift = {f: psi(ref[f].to_numpy(), feat[f].to_numpy()) for f in FEATURES}
for f, v in sorted(drift.items(), key=lambda x: -x[1])[:5]:
    print(f"  PSI {f:16s} {v:.3f} {'WARN' if v > 0.2 else 'ok'}")

# COMMAND ----------

# 5. Audiences (same rule as the local pipeline) -> a table the activation step can read
feat["risk"] = risk
value = feat.risk * SAVE_RATE * feat.spend * MARGIN - VOUCHER_COST
top_spend = feat.spend.quantile(0.9)
feat["audience"] = np.select(
    [value > 0, feat.risk >= 0.5, (feat.risk < 0.3) & (feat.spend >= top_spend)],
    ["winback_voucher", "reactivation_email", "vip_early_access"], default="no_action")
out = spark.createDataFrame(feat[["customer_id", "risk", "audience"]]).withColumn("cutoff", F.to_date(F.lit(CUTOFF)))
TABLE = "workspace.meridian.weekly_churn_audiences"
if spark.catalog.tableExists(TABLE):  # replace only this week's rows; other weeks stay (re-running a week is safe)
    out.write.mode("overwrite").option("replaceWhere", f"cutoff = DATE'{CUTOFF}'").saveAsTable(TABLE)
else:
    out.write.saveAsTable(TABLE)
print(feat.audience.value_counts().sort_index().to_string())
dbutils.notebook.exit(json.dumps({"cutoff": CUTOFF, "customers": len(feat), "mean_risk": round(float(risk.mean()), 4),
                                  "psi_max": round(max(drift.values()), 4), "audiences": feat.audience.value_counts().sort_index().to_dict()}))
