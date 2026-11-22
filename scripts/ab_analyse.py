# Analyse the A/B test: difference, 95% confidence interval, p-value, and an A/A sanity check
import polars as pl
import numpy as np
from scipy.stats import norm

df = pl.read_parquet("data/clean/ab_results.parquet")

def compare(a, b, label):
    p1, n1 = a.mean(), len(a)
    p2, n2 = b.mean(), len(b)
    diff = p1 - p2                                         # how much lower b's churn is
    se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)  # how much luck can move the gap
    lo, hi = diff - 1.96 * se, diff + 1.96 * se            # 95% confidence interval
    p_value = 2 * (1 - norm.cdf(abs(diff / se)))           # chance of a gap this big by luck alone
    print(f"{label}: {p1*100:.2f}% vs {p2*100:.2f}%  gap {diff*100:.2f} pts  "
          f"95% CI [{lo*100:.2f}, {hi*100:.2f}]  p-value {p_value:.4f}")
    return p1, lo, hi

control = df.filter(pl.col("group") == "control")["churned_after"].to_numpy()
voucher = df.filter(pl.col("group") == "voucher")["churned_after"].to_numpy()

# 1. The real test: control vs voucher
p_control, lo, hi = compare(control, voucher, "A/B control vs voucher")
print(f"   save rate: {(lo/p_control)*100:.1f}% to {(hi/p_control)*100:.1f}%  (planted truth 20%)")

# 2. A/A sanity check: two random halves of control (nobody got a voucher)
rng = np.random.default_rng(7)
half = rng.random(len(control)) < 0.5
compare(control[half], control[~half], "A/A control vs control  ")