# Two A/B traps: (1) peeking every day, (2) sample ratio mismatch (SRM)
import numpy as np
from scipy.stats import norm

# ---------- Trap 1: peeking (A/A tests: the voucher does NOTHING) ----------
rng = np.random.default_rng(3)
SIMS, DAYS, PER_DAY, P = 2000, 28, 500, 0.52
a = rng.binomial(PER_DAY, P, size=(SIMS, DAYS)).cumsum(axis=1)   # running total of churners, group A
b = rng.binomial(PER_DAY, P, size=(SIMS, DAYS)).cumsum(axis=1)   # running total of churners, group B
n = PER_DAY * np.arange(1, DAYS + 1)                             # customers per group so far, each day
pa, pb = a / n, b / n
se = np.sqrt(pa * (1 - pa) / n + pb * (1 - pb) / n)
significant = np.abs((pa - pb) / se) > 1.96                      # "p < 0.05" on each day of each test

print(f"Fooled when looking ONCE at day 28:    {significant[:, -1].mean()*100:.1f}%  (should be ~5%)")
print(f"Fooled when PEEKING every day:         {significant.any(axis=1).mean()*100:.1f}%")

# ---------- Trap 2: sample ratio mismatch ----------
def srm(n_a, n_b):
    total = n_a + n_b
    z = (n_a - total / 2) / np.sqrt(total * 0.25)
    p = 2 * (1 - norm.cdf(abs(z)))
    verdict = "OK" if p >= 0.001 else "SRM! investigate before trusting results"
    print(f"Split {n_a:,} vs {n_b:,}: p-value {p:.4f} -> {verdict}")

print()
srm(27244, 26918)     # our real test
srm(27244, 25800)     # a broken test (e.g. some vouchers bounced)