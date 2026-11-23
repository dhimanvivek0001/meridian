# Interview stories (STAR)

Eight stories from Meridian. Each one takes about 90 seconds to tell. The numbers are all in `docs/findings.md`.

**Which story for which question:**

| They ask… | Tell |
|---|---|
| "Tell me about a time you found the real cause of a problem" | 1 |
| "…you challenged an assumption" / "…a time you were wrong" | 2, 3 |
| "…you prevented a bad decision" | 4, 5 |
| "…attention to detail" / "…a bug you caught" | 6, 7 |
| "…a project that didn't work" | 8 |
| "How do you show business value?" | 3 + the CEO one-pager |

---

## 1. "It wasn't COVID": finding the real cause of the decline

- **S:** Sales fell 12% (15.52M → 13.64M items). Everyone's first guess was COVID.
- **T:** Find out whether that was true, and what the business could actually fix.
- **A:** I split the year into before COVID (Oct–Feb) and during COVID (Mar–Aug), each compared with the same months a year earlier. Then I drilled down: product groups, then types, then T-shirts, where I split sales into *designs × sales per design*.
- **R:** Sales were already −11% before COVID. Tops and trousers made up 92% of that loss. T-shirts fell −31%, mostly because we sold **20% fewer designs**. That is a buying decision we control, not a pandemic. Online, which everyone assumed was fine, was actually shrinking fastest.
- **Lesson:** test the obvious story before you accept it, and break totals into parts that multiply.

## 2. The regression that got the sign wrong

- **S:** I needed price elasticity to plan discounts.
- **T:** Estimate how much sales rise when the price drops.
- **A:** A regression on 2.2M item-weeks gave **+0.14**, meaning cutting prices *lowers* sales. I realised why: the business discounts items that are already selling badly (reactive pricing), so price and weak demand move together. I designed a randomised test: 9,320 items randomly given 0–40% off (simulated, with a planted elasticity so I could check the method).
- **R:** The test recovered the true elasticity of **−1.2**. It also showed that 40% off raises revenue by 10% but cuts profit by 63%. Per-item clearance beat a flat 50% sale by €10.7m a year (+€0.94m vs −€9.8m).
- **Lesson:** when the "treatment" is chosen because of the outcome, only an experiment gives the right answer.

## 3. Correcting my own number: €10.1m → €2.75m

- **S:** In the churn module I estimated that profit-based voucher targeting was worth a lot.
- **T:** Later, when building the company P&L, I had to put every lesson into the same € terms.
- **A:** I noticed my churn calculation had valued a saved customer at their **revenue**, not their **margin**. I re-ran it on margin, wrote the correction next to the original, and did not hide it.
- **R:** The value went from €10.1m to **€2.75m** a year, with 265k vouchers instead of 558k. All the models together are worth €3.73m (3% of margin). That is a smaller, believable number a CFO can trust.
- **Lesson:** consistent units across the business matter more than a big headline.

## 4. The optimizer's curse in marketing mix modelling

- **S:** The marketing mix model suggested re-splitting a €48k/day budget.
- **T:** Decide whether to trust the model's promised gain.
- **A:** Because I had simulated the spend with a known truth, I could check the plan. The model overrated search (338 vs a true 225) and email, and the optimizer pushed money exactly where the model was most wrong. Two channels hit the 200% cap, which is a red flag.
- **R:** It promised **+3,097 items/day**. The truth was **+119**, which is 26× smaller. The direction was right but the size was wrong. I recommended shifting only about 20% of the plan, running a geo lift test, then calibrating.
- **Lesson:** an optimizer amplifies model error. Test and learn instead of moving the whole budget.

## 5. "Never run out" destroys profit

- **S:** For stock ordering, the instinct is to buy enough to never run out.
- **T:** Find the order level that maximises profit.
- **A:** I built honest forecast ranges and checked that reality landed inside them 88% of the time. The quantile model's ranges only did 44%, so they were overconfident. Then I used the newsvendor rule: a shortage costs 0.50 and a leftover costs 0.40, so you order at about the 56th percentile.
- **R:** The newsvendor kept 84% of perfect-forecast profit. Ordering the "never run out" high case kept only 29%, which is about **−€65m a year**.
- **Lesson:** the best ML forecaster only tied a seasonal baseline (8.6% vs 8.4% WAPE). The money was in the *decision rule*, not the model.

## 6. A bug that showed a 782,410% error

- **S:** Building forecast baselines, one metric came out at **782,410% WAPE**.
- **T:** Find out whether the forecast was really that bad.
- **A:** I traced it to unsigned 32-bit integer columns. Subtracting a bigger number from a smaller one *wrapped around* to about 4 billion instead of going negative.
- **R:** Casting to float fixed it, and the real WAPE was 8.4%. I added the rule to my checklist: cast before subtracting counts.
- **Lesson:** an absurd number is a bug until proven otherwise.

## 7. Experiment tracking caught a hidden non-determinism

- **S:** I added MLflow tracking to the recommender. Two runs with the same code, data and seed gave **7,968 vs 7,938 hits**.
- **T:** Explain why "seeded" code wasn't reproducible.
- **A:** The popularity rank broke ties by row order, and Polars' group-by doesn't guarantee row order. I made the tie-break explicit (sales, then article id). Later, in the weekly pipeline, multi-threaded float sums differed in the 14th decimal and flipped customers at rule boundaries, so I rounded features to 9 decimals.
- **R:** Now every rerun is byte-identical. It also showed that the run-to-run noise (0.04 pts) was about a third of the ML ranker's whole gain over a simple rule.
- **Lesson:** a seed is not enough. Track runs and fingerprint outputs.

## 8. An honest negative: product photos didn't help

- **S:** I used CLIP to embed 1,935 product photos and add "looks like what you bought" candidates to the recommender.
- **T:** Show whether the photos actually helped.
- **A:** Recall rose from 23.96% to 24.55%, which looked like a win. So I ran a **fair control**: add the same number of extra *bestsellers* instead.
- **R:** The bestsellers reached **24.75%** and beat the photos. The ranker with visual features also dropped slightly. I recommended using the embeddings for **cold start** instead, where text plus photo picked new items at 3× random.
- **Lesson:** compare against a fair control with the same budget, not against "nothing".

---

### 30-second project pitch

> "Meridian is a fictional retailer built on 31 million real H&M transactions. I worked it end to end like an analytics team: I found the sales decline started before COVID and came from a cut T-shirt range; built churn, pricing, forecasting and recommender models; put a € value on each (€3.7m a year together); and shipped the churn scoring as a monitored weekly Databricks job. The thing I'm proudest of is the corrections: experiments that overturned a regression, an MMM that over-promised 26×, and my own number that I cut from €10m to €2.75m."
