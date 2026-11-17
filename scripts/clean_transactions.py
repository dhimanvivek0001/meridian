# Clean the transactions table: clear names, readable channel, add month.
import polars as pl

print("Cleaning transactions... (takes 1-3 minutes)")
tx = pl.scan_parquet("data/parquet/transactions.parquet")

clean = tx.select(
    pl.col("t_dat").alias("sale_date"),
    pl.col("t_dat").dt.truncate("1mo").alias("month"),
    pl.col("customer_id"),
    pl.col("article_id"),
    pl.col("price").alias("price_index"),
    pl.when(pl.col("sales_channel_id") == 1).then(pl.lit("store"))
    .when(pl.col("sales_channel_id") == 2).then(pl.lit("online"))
    .alias("sales_channel"),
)
clean.sink_parquet("data/clean/transactions.parquet")

# Automatic checks on the SAVED file
saved = pl.scan_parquet("data/clean/transactions.parquet")
rows_before = tx.select(pl.len()).collect().item()
rows_after = saved.select(pl.len()).collect().item()
assert rows_before == rows_after, "Rows were lost!"
empty_channels = saved.select(pl.col("sales_channel").null_count()).collect().item()
assert empty_channels == 0, "Some sales have no channel"

print("transactions cleaned:", rows_after, "rows")