# Databricks notebook source
from pyspark.sql import functions as F

cust = spark.table("workspace.meridian.bronze_customers")
silver_cust = (
    cust
    .withColumn("fashion_news_frequency", F.upper(F.coalesce(F.col("fashion_news_frequency"), F.lit("UNKNOWN"))))
    .withColumn("FN", F.coalesce(F.col("FN"), F.lit(0)).cast("tinyint"))
    .withColumn("Active", F.coalesce(F.col("Active"), F.lit(0)).cast("tinyint"))
    .withColumn("club_member_status", F.coalesce(F.col("club_member_status"), F.lit("UNKNOWN")))
    .withColumn("age_band",
        F.when(F.col("age").isNull(), "unknown")
         .when(F.col("age") < 25, "16-24")
         .when(F.col("age") < 35, "25-34")
         .when(F.col("age") < 45, "35-44")
         .when(F.col("age") < 55, "45-54")
         .otherwise("55+"))
)
assert silver_cust.count() == cust.count(), "Rows were lost!"
assert silver_cust.filter(F.col("FN").isNull()).count() == 0, "FN still has empty boxes"
silver_cust.write.mode("overwrite").saveAsTable("workspace.meridian.silver_customers")
print("silver_customers:", silver_cust.count())

# COMMAND ----------

tx = spark.table("workspace.meridian.bronze_transactions")
silver_tx = tx.select(
    F.col("t_dat").alias("sale_date"),
    F.trunc("t_dat", "month").alias("month"),
    "customer_id",
    "article_id",
    F.col("price").alias("price_index"),
    F.when(F.col("sales_channel_id") == 1, "store")
     .when(F.col("sales_channel_id") == 2, "online")
     .alias("sales_channel"),
)
assert silver_tx.count() == tx.count(), "Rows were lost!"
assert silver_tx.filter(F.col("sales_channel").isNull()).count() == 0, "Some sales have no channel"
silver_tx.write.mode("overwrite").saveAsTable("workspace.meridian.silver_transactions")
print("silver_transactions:", silver_tx.count())
silver_tx.groupBy("sales_channel").count().show()