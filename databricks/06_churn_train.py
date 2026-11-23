# Databricks notebook source
# MAGIC %md
# MAGIC Lesson 56: train the churn champion on Databricks, track it with Databricks MLflow, register it in Unity Catalog.

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
from lightgbm import LGBMClassifier
from mlflow.models import infer_signature
from sklearn.metrics import roc_auc_score

MODEL = "workspace.meridian.churn_model"           # Unity Catalog name: catalog.schema.model
PARAMS = {"n_estimators": 600, "learning_rate": 0.05, "num_leaves": 15}  # the local champion (L54, AUC 0.7965)
LOCAL_AUC = 0.7965
user = spark.sql("SELECT current_user()").first()[0]
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(f"/Users/{user}/meridian-churn")

train = make_labels("2020-06-02").toPandas().sort_values("customer_id")
test = make_labels("2020-07-28").toPandas().sort_values("customer_id")
assert len(train) == 988_844 and len(test) == 984_525, "same customers as the local L16/L19 data"
print(f"train {len(train):,} (churn {train.churned.mean():.1%}) | test {len(test):,} (churn {test.churned.mean():.1%})")

# COMMAND ----------

# Keep the training features as a table: the weekly scoring task compares each week against them (PSI drift)
spark.createDataFrame(train[["customer_id"] + FEATURES]).write.mode("overwrite").saveAsTable("workspace.meridian.churn_train_features")

with mlflow.start_run(run_name="L56 LightGBM v2 on Databricks") as run:
    model = LGBMClassifier(**PARAMS, random_state=42, verbose=-1)
    model.fit(train[FEATURES].to_numpy(), train.churned.to_numpy())
    risk = model.predict_proba(test[FEATURES].to_numpy())[:, 1]
    auc = roc_auc_score(test.churned, risk)
    top10 = test.churned.to_numpy()[risk >= np.quantile(risk, 0.9)].mean()
    mlflow.log_params(PARAMS | {"features": ",".join(FEATURES), "train_cutoff": "2020-06-02", "test_cutoff": "2020-07-28"})
    mlflow.log_metrics({"auc": auc, "top10_churn_rate": top10})
    print(f"Databricks AUC {auc:.4f} vs local {LOCAL_AUC} | riskiest 10% churn {top10:.1%} | mlflow {mlflow.__version__}")
    assert abs(auc - LOCAL_AUC) < 0.002, "Databricks model differs from the local one - check the feature port"
    sig = infer_signature(test[FEATURES].head(100), risk[:100])
    # We pin mlflow 3.18 above: serverless ships MLflow 2.x, where log_model has no name= and UC uploads fail on Free Edition
    mlflow.lightgbm.log_model(model, name="model", signature=sig, input_example=test[FEATURES].head(3),
                              registered_model_name=MODEL, pip_requirements=["lightgbm==4.7.0", "scikit-learn", "numpy"])

# COMMAND ----------

from mlflow import MlflowClient

client = MlflowClient()
latest = max(int(v.version) for v in client.search_model_versions(f"name = '{MODEL}'"))
client.set_registered_model_alias(MODEL, "champion", latest)
print(f"{MODEL} v{latest} is now @champion")
dbutils.notebook.exit(json.dumps({"auc": round(auc, 4), "top10_churn_rate": round(float(top10), 4), "version": latest,
                                  "train_rows": len(train), "test_rows": len(test), "mlflow": mlflow.__version__}))
