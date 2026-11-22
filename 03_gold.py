# Databricks notebook source
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE workspace.meridian.gold_customer_rfm AS
# MAGIC WITH base AS (
# MAGIC   SELECT customer_id,
# MAGIC          MAX(sale_date)            AS last_date,
# MAGIC          COUNT(DISTINCT sale_date) AS frequency,
# MAGIC          SUM(price_index)          AS monetary
# MAGIC   FROM workspace.meridian.silver_transactions
# MAGIC   WHERE sale_date >= DATE'2019-09-23'
# MAGIC   GROUP BY customer_id
# MAGIC ),
# MAGIC scored AS (
# MAGIC   SELECT *,
# MAGIC          DATEDIFF(DATE'2020-09-23', last_date) AS recency
# MAGIC   FROM base
# MAGIC ),
# MAGIC graded AS (
# MAGIC   SELECT *,
# MAGIC     CASE WHEN recency <= 30 THEN 5 WHEN recency <= 90 THEN 4 WHEN recency <= 180 THEN 3
# MAGIC          WHEN recency <= 270 THEN 2 ELSE 1 END AS R,
# MAGIC     CASE WHEN frequency >= 11 THEN 5 WHEN frequency >= 6 THEN 4 WHEN frequency >= 3 THEN 3
# MAGIC          WHEN frequency = 2 THEN 2 ELSE 1 END AS F,
# MAGIC     CASE WHEN monetary > 1.0 THEN 5 WHEN monetary > 0.49 THEN 4 WHEN monetary > 0.20 THEN 3
# MAGIC          WHEN monetary > 0.08 THEN 2 ELSE 1 END AS M
# MAGIC   FROM scored
# MAGIC )
# MAGIC SELECT *,
# MAGIC   CASE WHEN R >= 4 AND F >= 4 THEN 'Champions'
# MAGIC        WHEN R >= 4 AND F = 1  THEN 'New'
# MAGIC        WHEN R >= 3 AND F >= 3 THEN 'Loyal'
# MAGIC        WHEN R <= 2 AND F >= 3 THEN 'At risk'
# MAGIC        WHEN R <= 2 AND F <= 2 THEN 'Lost'
# MAGIC        ELSE 'Needs attention' END AS segment
# MAGIC FROM graded;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT segment, COUNT(*) AS customers
# MAGIC FROM workspace.meridian.gold_customer_rfm
# MAGIC GROUP BY segment
# MAGIC ORDER BY customers DESC;

# COMMAND ----------

for name in ["customer_clusters", "churn_scores", "voucher_list"]:
    df = spark.read.parquet(f"/Volumes/workspace/meridian/raw/{name}.parquet")
    df.write.mode("overwrite").saveAsTable(f"workspace.meridian.gold_{name}")
    print(name, df.count())

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE workspace.meridian.gold_customer_360 AS
# MAGIC SELECT
# MAGIC   c.customer_id,
# MAGIC   c.age, c.age_band, c.club_member_status, c.fashion_news_frequency, c.FN,
# MAGIC   r.recency, r.frequency, r.monetary, r.R, r.F, r.M, r.segment,
# MAGIC   CASE k.cluster WHEN 2 THEN 'VIPs' WHEN 1 THEN 'Regulars'
# MAGIC                  WHEN 3 THEN 'Recent light shoppers' WHEN 0 THEN 'One-timers' END AS cluster_name,
# MAGIC   s.risk AS churn_risk,
# MAGIC   s.risk_band AS churn_risk_band,
# MAGIC   CASE WHEN v.customer_id IS NOT NULL THEN 1 ELSE 0 END AS in_voucher_list
# MAGIC FROM workspace.meridian.silver_customers c
# MAGIC LEFT JOIN workspace.meridian.gold_customer_rfm r       ON c.customer_id = r.customer_id
# MAGIC LEFT JOIN workspace.meridian.gold_customer_clusters k  ON c.customer_id = k.customer_id
# MAGIC LEFT JOIN workspace.meridian.gold_churn_scores s       ON c.customer_id = s.customer_id
# MAGIC LEFT JOIN workspace.meridian.gold_voucher_list v       ON c.customer_id = v.customer_id;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT cluster_name,
# MAGIC        COUNT(*) AS customers,
# MAGIC        ROUND(AVG(churn_risk), 2) AS avg_risk,
# MAGIC        SUM(in_voucher_list) AS on_voucher_list
# MAGIC FROM workspace.meridian.gold_customer_360
# MAGIC GROUP BY cluster_name
# MAGIC ORDER BY customers DESC;