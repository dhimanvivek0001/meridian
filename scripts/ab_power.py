# Power & sample size: how many customers per group to detect a given save rate?
import numpy as np
from scipy.stats import norm

BASE = 0.52                        # control churn rate (from our A/B test)
Z = norm.ppf(0.975) + norm.ppf(0.80)   # 1.96 + 0.84: 5% false alarm, 80% power

def n_needed(save_rate):
    p1, p2 = BASE, BASE * (1 - save_rate)
    return int(np.ceil(Z**2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p1 - p2) ** 2))

print("save rate   churn gap   customers per group")
for s in [0.20, 0.10, 0.05, 0.02, 0.01]:
    print(f"   {s*100:4.0f}%     {BASE*s*100:5.2f} pts     {n_needed(s):>9,}")

# Prove it: 1,000 simulated tests with a 5% save rate and the calculated group size
rng = np.random.default_rng(1)
n = n_needed(0.05)
p1, p2 = BASE, BASE * 0.95
c = rng.binomial(n, p1, size=1000) / n         # control churn in each fake test
v = rng.binomial(n, p2, size=1000) / n         # voucher churn in each fake test
se = np.sqrt(c * (1 - c) / n + v * (1 - v) / n)
caught = (np.abs((c - v) / se) > 1.96).mean()
print(f"\nSimulation: {n:,} per group, true save rate 5% -> test caught it {caught*100:.1f}% of the time (target 80%)")