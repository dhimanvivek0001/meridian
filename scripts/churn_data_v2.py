# Churn data v2: same time split, plus smarter clues (recent trend, usual gap, overdue, customer info)
# Lesson 55: split into make_features() (used by the weekly pipeline) and make_data() (features + answers),
# and only build the training files when run as a script, so other scripts can import the feature logic.
import polars as pl
from datetime import date, timedelta

clean = pl.scan_parquet("data/clean/transactions.parquet")
cust = pl.scan_parquet("data/clean/customers.parquet").select(
    "customer_id",
    "age",
    "FN",
    (pl.col("club_member_status") == "ACTIVE").cast(pl.Int8).alias("club_active"),
    (pl.col("fashion_news_frequency") == "REGULARLY").cast(pl.Int8).alias("news_regular"),
)


def make_features(cutoff):
    """Clues for every customer who bought in the 12 months before `cutoff`, using only data before `cutoff` (lazy)."""
    start = cutoff.replace(year=cutoff.year - 1)
    w4 = cutoff - timedelta(weeks=4)       # start of the last 4 weeks
    w16 = cutoff - timedelta(weeks=16)     # start of the 12 weeks before that
    past = clean.filter((pl.col("sale_date") >= start) & (pl.col("sale_date") < cutoff))
    return (
        past
        .group_by("customer_id")
        .agg(
            pl.col("sale_date").min().alias("first_date"),
            pl.col("sale_date").max().alias("last_date"),
            pl.col("sale_date").n_unique().alias("visits"),
            pl.col("price_index").sum().alias("spend"),
            pl.len().alias("items"),
            (pl.col("sales_channel") == "online").mean().alias("online_share"),
            pl.col("sale_date").filter(pl.col("sale_date") >= w4).n_unique().alias("visits_4w"),
            pl.col("sale_date").filter((pl.col("sale_date") >= w16) & (pl.col("sale_date") < w4))
                .n_unique().alias("visits_prev12w"),
        )
        .with_columns(
            (pl.lit(cutoff) - pl.col("last_date")).dt.total_days().alias("days_since"),
            pl.when(pl.col("visits") > 1)
              .then((pl.col("last_date") - pl.col("first_date")).dt.total_days() / (pl.col("visits") - 1))
              .otherwise(365.0)
              .alias("avg_gap"),
        )
        .with_columns((pl.col("days_since") / pl.col("avg_gap")).alias("overdue"))
        .drop("first_date", "last_date")
        .join(cust, on="customer_id", how="left")
        .with_columns(pl.col("age").fill_null(pl.col("age").median()))
    )


def make_data(cutoff):
    start = cutoff.replace(year=cutoff.year - 1)
    end = cutoff + timedelta(weeks=8)
    past = clean.filter((pl.col("sale_date") >= start) & (pl.col("sale_date") < cutoff))
    future = clean.filter((pl.col("sale_date") >= cutoff) & (pl.col("sale_date") < end))

    # Answer: 1 = no purchase in the next 8 weeks
    stayed = future.select("customer_id").unique().with_columns(pl.lit(0).alias("churned"))
    labels = (
        past.select("customer_id").unique()
        .join(stayed, on="customer_id", how="left")
        .with_columns(pl.col("churned").fill_null(1))
    )
    return make_features(cutoff).join(labels, on="customer_id").collect()


if __name__ == "__main__":
    train = make_data(date(2020, 6, 2))
    test = make_data(date(2020, 7, 28))

    for name, df in [("train", train), ("test", test)]:
        assert df["churned"].null_count() == 0, f"{name} has empty answers"
        assert df["overdue"].null_count() == 0, f"{name} has empty overdue"
        print(name, df.height, "customers, churn rate", round(df["churned"].mean() * 100, 1), "%")

    train.write_parquet("data/clean/churn_train_v2.parquet")
    test.write_parquet("data/clean/churn_test_v2.parquet")
    print(test.select("visits_4w", "visits_prev12w", "avg_gap", "overdue", "age").describe())
