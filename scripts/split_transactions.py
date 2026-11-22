# Split transactions into one small parquet file per month, for easy upload to Databricks
import polars as pl
from pathlib import Path

out = Path("data/upload/transactions")
out.mkdir(parents=True, exist_ok=True)

tx = pl.scan_parquet("data/parquet/transactions.parquet")
months = tx.select(pl.col("t_dat").dt.strftime("%Y-%m").unique().sort()).collect()["t_dat"].to_list()

for m in months:
    tx.filter(pl.col("t_dat").dt.strftime("%Y-%m") == m).sink_parquet(out / f"transactions_{m}.parquet")
    print("saved", m)

total = pl.scan_parquet(str(out / "*.parquet")).select(pl.len()).collect().item()
assert total == 31788324, "Rows lost while splitting!"
print("All pieces together:", total, "rows")