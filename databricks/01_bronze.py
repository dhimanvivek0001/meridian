# Databricks notebook source
# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS workspace.meridian;
# MAGIC CREATE VOLUME IF NOT EXISTS workspace.meridian.raw;

# COMMAND ----------

paths = {
    "articles": "/Volumes/workspace/meridian/raw/articles.parquet",
    "customers": "/Volumes/workspace/meridian/raw/customers.parquet",
    "transactions": "/Volumes/workspace/meridian/raw/transactions/",
}
for name, path in paths.items():
    df = spark.read.parquet(path)
    df.write.mode("overwrite").saveAsTable(f"workspace.meridian.bronze_{name}")
    print(name, df.count())