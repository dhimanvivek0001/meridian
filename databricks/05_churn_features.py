# Databricks notebook source
# Lesson 56: churn v2 features in Spark - a line-by-line port of make_features() in scripts/churn_data_v2.py.
# Both 06_churn_train and 07_churn_score load this notebook with %run, so training and scoring use the SAME code.
from pyspark.sql import functions as F

FEATURES = ["days_since", "visits", "spend", "items", "online_share", "visits_4w", "visits_prev12w",
            "avg_gap", "overdue", "age", "FN", "club_active", "news_regular"]


def make_features(cutoff):
    """Clues for every customer who bought in the 12 months before `cutoff` ('YYYY-MM-DD'), using only data before it."""
    c = F.to_date(F.lit(cutoff))
    tx = spark.table("workspace.meridian.silver_transactions")
    cust = spark.table("workspace.meridian.silver_customers").select(
        "customer_id", "age", F.col("FN").cast("int").alias("FN"),
        (F.col("club_member_status") == "ACTIVE").cast("int").alias("club_active"),
        (F.col("fashion_news_frequency") == "REGULARLY").cast("int").alias("news_regular"),
    )
    w4, w16 = F.date_sub(c, 28), F.date_sub(c, 112)
    past = tx.filter((F.col("sale_date") >= F.add_months(c, -12)) & (F.col("sale_date") < c))
    feat = (
        past.groupBy("customer_id").agg(
            F.min("sale_date").alias("first_date"),
            F.max("sale_date").alias("last_date"),
            F.countDistinct("sale_date").alias("visits"),
            F.sum("price_index").alias("spend"),
            F.count("*").alias("items"),
            F.avg((F.col("sales_channel") == "online").cast("double")).alias("online_share"),
            F.countDistinct(F.when(F.col("sale_date") >= w4, F.col("sale_date"))).alias("visits_4w"),
            F.countDistinct(F.when((F.col("sale_date") >= w16) & (F.col("sale_date") < w4), F.col("sale_date"))).alias("visits_prev12w"),
        )
        .withColumn("days_since", F.datediff(c, "last_date"))
        .withColumn("avg_gap", F.when(F.col("visits") > 1, F.datediff("last_date", "first_date") / (F.col("visits") - 1)).otherwise(F.lit(365.0)))
        .withColumn("overdue", F.col("days_since") / F.col("avg_gap"))
        .drop("first_date", "last_date")
        .join(cust, "customer_id", "left")
    )
    median_age = feat.select(F.percentile("age", 0.5)).first()[0]  # exact median, like polars .median()
    # round floats to 9 decimals: Spark sums in parallel, so the last decimals can differ between runs (L55)
    return (feat.withColumn("age", F.coalesce(F.col("age"), F.lit(median_age)))
            .select("customer_id", *[F.round(F.col(f).cast("double"), 9).alias(f) for f in FEATURES]))


def make_labels(cutoff):
    """1 = bought in the 12 months before the cutoff but nothing in the 8 weeks after (L16 definition)."""
    c = F.to_date(F.lit(cutoff))
    tx = spark.table("workspace.meridian.silver_transactions")
    stayed = (tx.filter((F.col("sale_date") >= c) & (F.col("sale_date") < F.date_add(c, 56)))
              .select("customer_id").distinct().withColumn("stayed", F.lit(1)))
    return (make_features(cutoff).join(stayed, "customer_id", "left")
            .withColumn("churned", F.when(F.col("stayed").isNull(), 1).otherwise(0)).drop("stayed"))
