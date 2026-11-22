# Databricks notebook source
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE workspace.meridian.gold_audiences AS
# MAGIC SELECT * FROM (
# MAGIC   SELECT customer_id, segment, cluster_name, churn_risk, FN AS can_email,
# MAGIC     CASE
# MAGIC       WHEN in_voucher_list = 1 AND churn_risk >= 0.5 AND segment IN ('Champions', 'Loyal', 'At risk')
# MAGIC            THEN 'winback_voucher'
# MAGIC       WHEN cluster_name = 'VIPs' THEN 'vip_early_access'
# MAGIC       WHEN segment = 'New'       THEN 'second_purchase'
# MAGIC       WHEN segment = 'Lost'      THEN 'reactivation_email'
# MAGIC     END AS audience
# MAGIC   FROM workspace.meridian.gold_customer_360
# MAGIC )
# MAGIC WHERE audience IS NOT NULL;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT audience,
# MAGIC        COUNT(*)                          AS customers,
# MAGIC        SUM(can_email)                    AS can_email,
# MAGIC        ROUND(AVG(churn_risk), 2)         AS avg_risk
# MAGIC FROM workspace.meridian.gold_audiences
# MAGIC GROUP BY audience
# MAGIC ORDER BY customers DESC;
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE VOLUME IF NOT EXISTS workspace.meridian.exports;

# COMMAND ----------

from pyspark.sql import functions as F

aud = spark.table("workspace.meridian.gold_audiences").filter(F.col("can_email") == 1)
for name in ["winback_voucher", "vip_early_access", "second_purchase", "reactivation_email"]:
    (aud.filter(F.col("audience") == name)
        .select(F.col("customer_id").alias("external_id"), "audience", F.round("churn_risk", 3).alias("churn_risk"))
        .coalesce(1)
        .write.mode("overwrite").option("header", True)
        .csv(f"/Volumes/workspace/meridian/exports/{name}"))
    print(name, aud.filter(F.col("audience") == name).count())