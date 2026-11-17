# Clean the customers table: fix spelling, fill empty boxes, add age groups.
import polars as pl

print("Cleaning customers...")
cust = pl.read_parquet("data/parquet/customers.parquet")

clean = cust.with_columns(
    pl.col("fashion_news_frequency").str.to_uppercase().fill_null("UNKNOWN"),
    pl.col("FN").fill_null(0).cast(pl.Int8),
    pl.col("Active").fill_null(0).cast(pl.Int8),
    pl.col("club_member_status").fill_null("UNKNOWN"),
    pl.when(pl.col("age").is_null()).then(pl.lit("unknown"))
    .when(pl.col("age") < 25).then(pl.lit("16-24"))
    .when(pl.col("age") < 35).then(pl.lit("25-34"))
    .when(pl.col("age") < 45).then(pl.lit("35-44"))
    .when(pl.col("age") < 55).then(pl.lit("45-54"))
    .otherwise(pl.lit("55+"))
    .alias("age_band"),
)

# Automatic checks: if any is false, the script STOPS with the message.
assert clean.height == cust.height, "Rows were lost!"
assert clean["FN"].null_count() == 0, "FN still has empty boxes"
assert clean["Active"].null_count() == 0, "Active still has empty boxes"
assert clean["club_member_status"].null_count() == 0, "Club status still has empty boxes"
assert "None" not in clean["fashion_news_frequency"].to_list(), "Spelling problem not fixed"

clean.write_parquet("data/clean/customers.parquet")
print("customers cleaned:", clean.shape)