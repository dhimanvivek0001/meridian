# K-means segments: let the computer group customers by recency, frequency, monetary
import polars as pl
from sklearn.cluster import KMeans

seg = pl.read_parquet("data/clean/customer_segments.parquet")

# 1. Squash the giants (log)
prep = seg.select(
    "customer_id", "segment", "recency", "frequency", "monetary",
    pl.col("recency").log1p().alias("r_log"),
    pl.col("frequency").log1p().alias("f_log"),
    pl.col("monetary").log1p().alias("m_log"),
)

# 2. Same ruler: (value - normal) / usual wiggle
scaled = prep.with_columns(
    ((pl.col("r_log") - pl.col("r_log").mean()) / pl.col("r_log").std()).alias("r_z"),
    ((pl.col("f_log") - pl.col("f_log").mean()) / pl.col("f_log").std()).alias("f_z"),
    ((pl.col("m_log") - pl.col("m_log").mean()) / pl.col("m_log").std()).alias("m_z"),
)

# 3. K-means: 4 groups
X = scaled.select("r_z", "f_z", "m_z").to_numpy()
km = KMeans(n_clusters=4, random_state=42, n_init=10)
scaled = scaled.with_columns(pl.Series("cluster", km.fit_predict(X)))

# 4. Describe each group in normal numbers
profile = (
    scaled
    .group_by("cluster")
    .agg(
        pl.len().alias("customers"),
        pl.col("recency").median().alias("days"),
        pl.col("frequency").median().alias("visits"),
        pl.col("monetary").median().round(2).alias("spend"),
        pl.col("monetary").sum().alias("total_spend"),
    )
    .with_columns(
        (pl.col("customers") / pl.col("customers").sum() * 100).round(1).alias("pct_customers"),
        (pl.col("total_spend") / pl.col("total_spend").sum() * 100).round(1).alias("pct_spend"),
    )
    .sort("spend", descending=True)
)

# 5. Check: everyone has a group
assert profile["customers"].sum() == seg.height, "Some customers have no cluster"

print(profile)
profile.write_csv("reports/kmeans_profile.csv")
scaled.select("customer_id", "segment", "cluster").write_parquet("data/clean/customer_clusters.parquet")
print("Saved reports/kmeans_profile.csv and data/clean/customer_clusters.parquet")