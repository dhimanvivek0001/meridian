# Churn data: clues from the 12 months before a cutoff, answer = no purchase in the 8 weeks after
import polars as pl
from datetime import date, timedelta

clean = pl.scan_parquet("data/clean/transactions.parquet")

def make_data(cutoff):
    start = cutoff.replace(year=cutoff.year - 1)      # same date, one year earlier
    end = cutoff + timedelta(weeks=8)                 # 8 weeks after the cutoff
    past = clean.filter((pl.col("sale_date") >= start) & (pl.col("sale_date") < cutoff))
    future = clean.filter((pl.col("sale_date") >= cutoff) & (pl.col("sale_date") < end))

    # Answer: 1 = no purchase in the next 8 weeks
    stayed = future.select("customer_id").unique().with_columns(pl.lit(0).alias("churned"))
    labels = (
        past.select("customer_id").unique()
        .join(stayed, on="customer_id", how="left")
        .with_columns(pl.col("churned").fill_null(1))
    )

    # Clues: from the past only
    features = (
        past
        .group_by("customer_id")
        .agg(
            pl.col("sale_date").max().alias("last_date"),
            pl.col("sale_date").n_unique().alias("visits"),
            pl.col("price_index").sum().alias("spend"),
            pl.len().alias("items"),
            (pl.col("sales_channel") == "online").mean().alias("online_share"),
        )
        .with_columns((pl.lit(cutoff) - pl.col("last_date")).dt.total_days().alias("days_since"))
        .drop("last_date")
    )
    return features.join(labels, on="customer_id").collect()

train = make_data(date(2020, 6, 2))
test = make_data(date(2020, 7, 28))

for name, df in [("train", train), ("test", test)]:
    assert df["churned"].null_count() == 0, f"{name} has empty answers"
    print(name, df.height, "customers, churn rate", round(df["churned"].mean() * 100, 1), "%")

train.write_parquet("data/clean/churn_train.parquet")
test.write_parquet("data/clean/churn_test.parquet")
print("Saved churn_train and churn_test")