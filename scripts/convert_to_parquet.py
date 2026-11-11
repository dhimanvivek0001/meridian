import polars as pl

print("Converting articles...")
articles = pl.read_csv(
    "data/raw/articles.csv",
    schema_overrides={"article_id": pl.Utf8, "product_code": pl.Utf8},
)
articles.write_parquet("data/parquet/articles.parquet")
print("articles done:", articles.shape)


print("Converting customers...")
customers = pl.read_csv(
    "data/raw/customers.csv",
    schema_overrides={"customer_id": pl.Utf8, "postal_code": pl.Utf8},
)
customers.write_parquet("data/parquet/customers.parquet")
print("customers done:", customers.shape)

print("Converting transactions... (takes 2-5 minutes)")
pl.scan_csv(
    "data/raw/transactions_train.csv",
    schema_overrides={"t_dat": pl.Date, "customer_id": pl.Utf8, "article_id": pl.Utf8},
).sink_parquet("data/parquet/transactions.parquet")
print("transactions done")