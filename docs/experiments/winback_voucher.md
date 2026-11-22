# Experiment: winback voucher (M4)

> Note: outcomes are SIMULATED on real customers with a planted true save rate of 20%, so we can check the method recovers it.

## Part 1: Design doc (written before the test)

| Item | Decision |
|---|---|
| Question | Does a winback voucher reduce churn among valuable at-risk customers? |
| Audience | winback_voucher audience, email consent only: 54,162 customers |
| Split | Random 50/50 coin flip: control (no voucher) vs voucher |
| Primary metric | 8-week churn rate (no purchase in the 8 weeks after 28 Jul 2020) |
| Baseline | ~52% churn expected in control |
| Smallest effect worth detecting | 5% save rate -> needs 5,801 per group (5% false alarms, 80% power) |
| Sample used | ~27,000 per group (whole consented audience), enough to detect ~2.3% |
| Duration | 8 weeks, analysed ONCE at the end (no peeking) |
| Checks before reading results | SRM test on the split (p < 0.001 = stop and investigate); A/A check |
| Decision rule | SHIP if churn reduction is significant (p < 0.05) AND the save-rate 95% CI lower bound is at least 10% |

## Part 2: Readout (after the test)

| Item | Result |
|---|---|
| Groups | control 27,244 / voucher 26,918 |
| SRM check | p = 0.16 -> OK |
| A/A check | gap -0.59 pts, 95% CI [-1.77, 0.60], p = 0.33 -> no fake effect |
| Churn | control 52.05% vs voucher 41.99% |
| Effect | -10.05 pts, 95% CI [-10.89, -9.22], p < 0.0001 |
| Save rate | 19.3% (95% CI 17.7% to 20.9%); planted truth 20% recovered |

### Decision: SHIP
Both rules are met: the effect is significant and the save-rate lower bound (17.7%) is above 10%.

### Recommendations
1. Roll the voucher out to the full winback audience.
2. Keep a small random holdout (e.g. 5%) with no voucher, to keep measuring the effect over time.
3. Our test was much bigger than needed (358 per group detects a 20% effect). Future strong offers can be tested on smaller groups, so fewer customers miss out.
4. Next question: target customers whose behaviour the voucher CHANGES (uplift), not just high-risk ones. Many VIPs would stay anyway.
