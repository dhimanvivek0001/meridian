\# Meridian findings



\## Lesson 1: first look at the raw data (10 Nov 2026)



1\. The 3 files link together by IDs.

&#x20;  - transactions.customer\_id -> customers.customer\_id (who bought)

&#x20;  - transactions.article\_id -> articles.article\_id (what they bought)

&#x20;  - Example: customer 000058a12d5b... bought 2 items online on 2018-09-20.

&#x20;    In the customers file she is 24, an ACTIVE club member, no newsletter.



2\. Missing data exists.

&#x20;  - In customers, FN and Active are often empty (,,).

&#x20;  - Need to decide later what empty means (probably "no").



3\. One product design has many colours.

&#x20;  - Same product\_code (0108775 = "Strap top") has different article\_ids

&#x20;    (0108775015 = black, 0108775044 = white).



4\. article\_id starts with a zero (0108775015).

&#x20;  - Must be stored as TEXT, not a number, or the zero is lost.



5\. Prices are disguised (e.g. 0.0508), not euros.

&#x20;  - Can compare prices, but cannot say "this costs 5 euros".

@'



\## Lesson 4: clean tables + first monthly report

\- Channel 1 = store, 2 = online (proved: channel 1 = 0 sales in April 2020 lockdown)

\- Peak month: June (both years). Low: winter. Strong seasonality.

\- Partial months: Sep 2018 (from 20th) and Sep 2020 (to 22nd). Never compare them to full months.

\- Sales were already falling BEFORE COVID: Oct -18%, Jan -15%, Feb -13% year-over-year.

\- April 2020 vs April 2019: -9% (shops closed; online +30% but couldn't fully replace stores)

'@ | Add-Content -Encoding utf8 docs\\findings.md


## Lesson 5: year-over-year report
- Average YoY change (Oct 2019 - Aug 2020, full months only): -11.7%
- Before COVID (Oct 2019 - Feb 2020): about -10.8%. During COVID (Mar - Aug 2020): about -12.4%.
- Conclusion: decline is NOT mainly COVID; most of it already existed.
- Partial months (Sep 2019 +106%, Sep 2020 -35%) are fake jumps and were removed.

## Lesson 6: sales drivers (items = customers x visits per customer x items per visit)
- Definition: 1 visit = 1 customer shopping on 1 day.
- Yearly average change: customers -4.7%, visits per customer -2.7%, items per visit -4.6%.
- Before COVID: smaller baskets were the main problem (-6.2% avg, negative every month).
- Lockdown (Mar-Apr 2020): far fewer customers (-13%) but bigger online baskets (+14% in April).
- After reopening: small baskets returned (-9% to -15%). Shrinking baskets = the long-term problem.

## Lesson 7: which products lost sales (Oct 2019-Aug 2020 vs Oct 2018-Aug 2019)
- Total: 15.52M -> 13.64M items (-12%).
- Upper body -991k (-16%) = 53% of the loss. Lower body -506k (-15%) = 27%. Tops + trousers = ~80% of the loss.
- Swimwear -20% (likely no-holiday COVID summer). Shoes -25% but only -99k items.
- Grew: underwear +3.9%, nightwear +5.6%, Other (H&M Home etc.) +240% from a tiny base. At-home shopping.
- Lesson: sort by items lost, not by %. Big % on a small group can matter less.
- Next question: were tops and trousers already falling BEFORE COVID?

## Lesson 8: was it COVID? (Oct-Feb before covid, Mar-Aug during, each vs same months a year earlier)
- Whole shop: before covid -11.1%, during covid -12.8%. Sales were already falling before covid.
- Upper body: -14.8% before, -17.4% during. Lower body: -15.8% before, -13.8% during.
- Tops + trousers = 637k of the 691k items lost BEFORE covid (92%). This is a product problem, not COVID.
- Shoes ~-25% in both periods. Swimwear -25% before covid (my no-holiday guess was wrong).
- Dresses (full body): +13.3% before, -6.9% during. The only group COVID really hurt.
- Underwear and nightwear grew in both periods, faster during covid.
- Lesson: split the data to test guesses. Totals vs average of monthly % give slightly different numbers.
- Next question: WHICH tops and trousers are failing?

## Lesson 9: which tops are failing? (before covid: Oct19-Feb20 vs Oct18-Feb19)
- Tops lost 420,583 items. Check: totals match Lesson 8 (2,850,711 -> 2,430,128).
- Sweater -135,631 (-14.0%), T-shirt -116,109 (-31.4%), Blouse -70,434 (-22.9%). Together 77% of the tops loss.
- Average for tops is -14.8%. Sweaters fall at the average (big only because they are the biggest type).
- T-shirts fall TWICE as fast (-31%) = the real outlier. Blouses also worse than average.
- Growing: Top +5.1%, Bodysuit +44.6%, Blazer +8.1%, Coat +4.1%.
- Guess (not tested yet): customers moving from basic T-shirts to fashion tops, or buying basics elsewhere.
- Lesson: compare each part to the average to find the real outlier, not just the biggest number.
- Next question: WHY are T-shirts failing? Fewer T-shirts in the range, or each T-shirt selling less?

## Lesson 10: why are T-shirts failing? (before covid, items = designs x items per design)
- Items 369,475 -> 253,366 (-31.4%). Check matches Lesson 9.
- Designs sold 3,751 -> 2,995 (-20.2%, 756 fewer designs).
- Items per design 98.5 -> 84.6 (-14.1%), about the same as all tops (-14.8%).
- So demand per T-shirt falls like everything else. The EXTRA drop comes from fewer designs on sale.
- About 60% of the T-shirt drop = fewer designs, 40% = each design selling less.
- Business: range cut is a buying decision we control. Restoring T-shirt range = quickest fix.
- Caveat: designs with zero sales are invisible; no stock data to fully prove removal.
- Lesson: len() counts rows, n_unique() counts different values. Split a total into parts that multiply.

## Lesson 11: do customers come back? (cohort retention)
- 1,362,281 customers bought at least once (9,699 signed up but never bought).
- Data starts 20 Sep 2018, so Sep-Dec 2018 'new' customers are mostly old regulars (left-censoring). Used cohorts Mar-Dec 2019 only.
- Apr 2020 jump in new customers (40,689) = lockdown first-time online buyers.
- Only 12-20% of new customers buy again next month. Loyal core ~10-15%.
- Column view makes late-2019 cohorts look worse, but the DIAGONAL shows every cohort dropped together in Aug 2019 = calendar effect, not worse customers.
- Matches Lesson 6: from autumn 2019 all customers come back less often.
- Lesson: read cohort grids by rows, columns AND diagonals. Always check the first months of any dataset.
- Next: Lesson 12 State of Meridian one-pager (closes M1), then M2/M3 (segments, churn).

## Lesson 12a: store vs online (before covid Oct-Feb, during covid Mar-Aug, vs a year earlier)
- Checks: store + online = Lesson 8 totals for all 4 periods.
- Online = ~69% of items. Store ~31%.
- Before covid: store -9.1% (-175k), online -12.0% (-516k). Online = 75% of the pre-covid loss.
- During covid: store -26.7% (lockdown), online -6.6%. Online did NOT grow even with stores closed.
- Business: the bigger, future channel (online) was shrinking fastest. Fixing online is the priority.
- Lesson: test the obvious guess ('stores are dying') - the data said the opposite.

## Lesson 13: RFM segments (M2 starts) - customers active 23 Sep 2019 to 22 Sep 2020
- 994,320 active customers. Median: last bought 86 days ago, 2 visits, spend 0.20.
- Skew: mean > median for frequency (4.4 vs 2) and spend (0.42 vs 0.20). A few super-fans (225 visits) pull the average up. Use median for 'typical'.
- Top customers are real super-fans (normal spend per visit, just very frequent). Kept.
- Champions 22% of customers = 59% of spend. Champions + Loyal = 45% of customers = 81% of spend (80/20 rule).
- At risk: 37,568 customers, spend each 0.37 (close to Loyal 0.41) and going quiet = best win-back target.
- New: 83,589, but only ~1 in 6 return (Lesson 11) = need a second-purchase offer.
- Lesson: scores need cut-offs, which create edges (0.20239 vs 0.19999). Next: let the computer find groups (K-means).

## Lesson 14: K-means (first ML model) - computer finds customer groups by itself
- Prep: log1p to shrink giants (225 visits -> 5.4), then scale (value - mean) / std so days, visits, money count equally.
- 4 groups found:
  - VIPs: 11% of customers, last bought 15 days ago, 13 visits = 47% of money.
  - Regulars: 25%, 65 days, 5 visits = 30% of money.
  - Recent light shoppers: 15%, 16 days, 3 visits, low spend = 8%. Best group to grow.
  - One-timers: 49%, 177 days, 1 visit = 15%. Half of customers bought once and left.
- Same story as hand-made RFM (small group = most money). K-means gives a tighter top group (11% vs 22%).
- Lesson: always shrink + scale before K-means. Name clusters by reading their medians.

## Lesson 15: simple CLV - does last year predict next year?
- Year 1 = 20 Sep 2018 to 22 Sep 2019, Year 2 = 23 Sep 2019 to 22 Sep 2020. 1,007,813 Year-1 buyers cut into 5 equal bands.
- Came back in Year 2: 36% (lowest band) up to 93% (highest band).
- Next-year value: top band 1.04 vs bottom band 0.07 = about 15x.
- Top 20% of last year's spenders = ~59% of next year's money (from these customers).
- Regression to the mean: top band fell 1.52 -> 1.04, bottom band rose 0.04 -> 0.07. Don't value customers on last year alone.
- Lesson: test a prediction with a past year you can check (Year 1 -> Year 2). qcut = equal-size bands. (condition).mean() = share of True.

## Lesson 16: first churn model (M3 starts)
- Churn = bought in the 12 months before the cutoff, but nothing in the next 8 weeks. Definition is a choice (8 weeks is short for 2-visits-a-year shoppers).
- Time split: train cutoff 2 Jun 2020 (988,844 customers, 63.5% churn), test cutoff 28 Jul 2020 (984,525, 67.3% churn). No peeking at the future.
- Logistic regression: accuracy 75.3% vs lazy-guess baseline 67.3%. AUC 0.792.
- Risk bands climb smoothly: safest 10% = 19.6% churn, riskiest 10% = 92.4%.
- Weights: visits -0.90 (strongest, more visits = stays), days_since +0.34, online_share +0.17 (online shoppers churn more), spend tiny (overlaps with visits/items).
- Trap: the riskiest band is mostly already gone and low value. Next: target by expected profit (risk x value), not risk alone.

## Lesson 17: who is worth saving? (expected profit targeting)
- Expected profit = risk x save rate x value - cost. Assumed save rate 20%, voucher cost 0.02 (to be tested in M4).
- Contact everyone: 984,525 vouchers, +13,375.
- Riskiest 10% only: -583 (LOSES money: mostly low-value people already gone).
- Only if profit > 0: 558,456 vouchers, +17,173 = 28% more profit with 426k fewer vouchers.
- Lesson: pick a threshold by expected profit, not by risk or accuracy. Write assumptions down clearly.

## Lesson 18: LightGBM vs logistic regression
- LightGBM (300 trees, boosting): AUC 0.793, accuracy 75.3%. Logistic regression: AUC 0.792, 75.3%. No real gain.
- With only 5 clues, both models hit the same limit. The limit is the clues, not the model.
- Decision: keep the simpler model (easier to explain and run). Next: better clues (feature engineering).

## Lesson 19: better clues (feature engineering)
- Added 8 clues: visits_4w, visits_prev12w, avg_gap, overdue (days_since / usual gap), age, FN, club_active, news_regular.
- AUC: logistic 0.792 -> 0.795, LightGBM 0.793 -> 0.796. Small real gain.
- LightGBM importance: visits 84.6%, days_since 5.3%, online_share 2.5%, overdue 1.5%, rest under 1.2% each. New clues mostly repeat what visits already says.
- Ceiling ~0.80: for 2-visits-a-year shoppers, buying in a given 8 weeks is partly random timing.
- Decision: stop tuning. Future idea: a longer churn window (6 months) is likely more predictable.

## Lesson 20: why is THIS customer at risk? (SHAP pushes) - closes M3
- LightGBM pred_contrib=True splits one customer's risk into a push per clue (+ = towards leaving, - = towards staying).
- Example: top-10% spender, risk 0.62, really churned. UP: age 61 (+0.19), online-only (+0.15). DOWN: 33 items (-0.18), bought 35 days ago (-0.12), reads fashion news (-0.12).
- Story: online-only burst shopper, usual gap ~20 days, now 1.8x overdue with no visit in 4 weeks -> online win-back email.
- Cautions: pushes explain the MODEL, not real-world causes. Ignore small pushes; use the top 2-3.
- M3 summary: churn model AUC ~0.80, beats baseline, profit-based targeting +28% profit, reasons per customer.

## Lesson 21: Databricks lakehouse (M0 part 2)
- Uploaded raw parquet to Unity Catalog volume workspace.meridian.raw (transactions split into 25 monthly files: 470 MB failed as one upload).
- Bronze: bronze_articles 105,542 / bronze_customers 1,371,980 / bronze_transactions 31,788,324 (match laptop).
- Silver (Spark): silver_customers, silver_transactions - same rules as Lessons 3-4. Online 22.4M / store 9.4M.
- Gold (SQL): gold_customer_rfm - segment counts match Lesson 13 exactly. Plus clusters, churn scores, voucher list.
- gold_customer_360: one row per customer (1,371,980) with segment, cluster, churn risk, voucher flag. Clusters and churn risk agree (VIPs 0.24 -> One-timers 0.79).
- Job meridian_weekly: bronze -> silver -> gold with dependencies, scheduled Monday 06:00. First run succeeded in 2m 4s.
- Noticed: 92% of VIPs get a voucher but most would stay anyway -> uplift problem for M4/M5.

## Lessons 22-23: M3.5 Activation (audiences + reverse ETL)
- gold_audiences: one audience per customer by priority rule: winback_voucher 146,370 / vip_early_access 105,788 / second_purchase 83,585 / reactivation_email 215,931.
- Consent (FN opt-in) cuts reachable customers from 551,674 to 198,161 (36%). VIPs opt in most (49%). Growing opt-in may beat model improvements.
- Exported one CSV per audience (consent only) from Databricks volume workspace.meridian.exports.
- File-name mix-up caught by checking the audience column inside each file. Push script reads audience from INSIDE the file.
- Mock ad platform (FastAPI): 10,000 IDs per request limit. push_audiences.py sent all 4 audiences in 22 batches, totals match exactly.
- Idempotent: re-running the push keeps the same totals (no duplicates).
- Real-world note: Meta/Google match on hashed email/phone from the CRM; our data only has anonymous IDs.

## Lessons 24-25: M4 A/B test of the winback voucher (simulated, planted truth 20%)
- Coin-flip split of the emailable winback audience: control 27,244 / voucher 26,918.
- Churn: control 52.05% vs voucher 41.99%. Gap 10.05 pts, 95% CI [9.22, 10.89], p < 0.0001.
- Save rate recovered: 17.7% to 20.9% (planted truth 20% inside the range). Confirms the Lesson 17 assumption.
- A/A check (two halves of control): gap -0.59, CI [-1.77, 0.60], p = 0.33. No fake effect, setup is fair.
- Lessons: randomisation removes selection bias; always report effect + CI + p-value; run an A/A sanity check.

## Lesson 26: power and sample size
- 5% false-alarm rate, 80% power, base churn 52%. Customers per group: 20% save -> 358, 10% -> 1,448, 5% -> 5,801, 2% -> 36,248, 1% -> 144,955.
- Halving the detectable effect needs 4x the sample (gap squared in the formula).
- Simulation check: 1,000 fake tests at 5,801 per group caught a real 5% effect 78.9% of the time (target 80%).
- Our test (27k per group) was far bigger than needed for a 20% effect; minimum detectable save rate ~2.3%. A big control group means lost saves.
- A 1% effect needs ~290k people: more than the whole emailable audience -> can't test reliably.

## Lesson 27: A/B traps - peeking and sample ratio mismatch
- 2,000 simulated A/A tests (no real effect), 28 days, 500/day/group: looking once at the end fooled 4.9% (expected ~5%); peeking daily and stopping at first p<0.05 fooled 27.6% (5.6x more fake wins).
- Fix: fix sample size up front, look once (or use sequential testing with stricter early thresholds).
- SRM check: our split 27,244 vs 26,918 -> p = 0.16, OK. Broken example 27,244 vs 25,800 -> p < 0.0001, SRM.
- Rule: check the split (SRM p < 0.001 = investigate) BEFORE reading any results.

## Lesson 29: uplift modelling (M5 part 1) - who does the voucher actually change?
- 4 types: sure things, persuadables, lost causes, sleeping dogs. Only persuadables are worth a voucher.
- Simulated experiment with planted truth: online light shoppers (online_share >= 0.5, visits <= 4) save 35%, others 5%. Observed: 34% vs 6%.
- T-learner: LightGBM on control + LightGBM on voucher group; uplift = p(churn without) - p(churn with). Random 50/50 train/test split.
- Ranked by uplift: top 20% real effect 22.5 pts, 96% persuadables; bottom 40% ~3-5 pts.
- Ranked by churn risk: blurrier (18.5 -> 3.3 pts); low-risk band has persuadables but nothing to save.
- Top 40% targeting: uplift 21.2 pts vs risk 17.7 pts = ~20% more customers saved per voucher.
- Uplift models need randomised experiment data (M4 first). Small bands are noisy (+-1-2 pts).

## Lessons 30-32: marketing mix modelling (M5 part 2, simulated spend with planted truth)
- Simulated 4 channels on real daily sales: TV bursts, social, search (follows demand), email. Planted adstock + saturation. Truth (items per EUR 1k): search 225 > email 190 > social 158 > TV 89.
- Fit: adstock + saturation per channel, settings searched with scipy minimize, regression with trend/weekday/month controls.
- Confounding: naive MMM credited search with ~3,650 (16x truth). Adding a demand control (search-trends index) -> ~338.
- Identifiability: v1 email only on Mondays (collinear with Monday effect) and social nearly constant -> estimates 48 and 1,517 (nonsense).
- v2 varied spend (social high/low days, email random days): social 171 (+8%), email 308, TV 76, search 338. Ranking of all 4 channels correct.
- Lessons: control for demand, spend must vary to be measurable, calibrate remaining bias with lift tests (experiments) / Bayesian priors.

## Lesson 33 - MMM budget plan (closes M5)
- Same budget (EUR 47,962/day) re-split with the fitted MMM, each channel kept within 50-200% of today.
- Plan: TV -11,701, social -458, search +10,892, email +1,267 (search and email hit the 200% cap = red flag).
- Model promised +3,097 items/day; truth was only +119/day (+43,488/year), about 26x over-promised.
- Why: the model overrated search (338 vs true 225) and email (308 vs 190), and the optimizer exploits model errors ("optimizer's curse").
- Direction was right (TV -1,020 items, search +927, email +261), but the size was wrong.
- Recommendation: shift about 20% of the plan, run a geo lift test on search, calibrate the MMM, then move more (test-and-learn).

## Lesson 34 - Price vs units (M6 starts)
- 2,210,899 item-weeks; discount = 1 - week price / item's highest price.
- Raw view: 0-5% off sells 17.8/week but 50%+ off only 8.3 - looks like discounts HURT (confounding: H&M discounts the items that are already failing).
- Within-item lift: 5-15% off = 1.15x the item's own normal (first sign of elasticity); deep discounts still 0.84-0.90.
- Remaining trap = lifecycle: deep markdowns happen when an item is old and demand is dying anyway.
- Next: regression with item + week + item age to get clean elasticity per product group.

## Lesson 35 - Elasticity regression and markdown event study
- Regression (item + week normals removed, item age clue): elasticity +0.14 = WRONG sign; age effect -0.24 (older sells less, sensible).
- Why: reactive pricing - H&M marks down BECAUSE sales fall. Event study: lift 1.18 -> 1.05 -> 1.03 -> 0.92 in the 4 weeks before the first markdown.
- Markdown works: lift 0.92 -> 1.41 (+53%) in the markdown week, fading to 1.09 by week +4.
- Still not clean (markdowns overlap the Jan/Jul sale season); the only clean answer is a randomised price test.

## Lesson 36 - Randomised price test
- 9,320 items (5+ sales/week in Aug 2020) randomly given 0/10/20/30/40% off; planted elasticity -1.2.
- Test recovered the truth: lifts 1.00 / 1.14 / 1.31 / 1.53 / 1.83 (randomisation removes reactive-pricing bias; regression had said +0.14).
- Revenue trap: 40% off = revenue +10% but profit -63% (cost = 50% of full price). Best in-season profit = no discount.
- Break-even: at 50% cost, 10% off only pays if sales rise 25%+ (elasticity about -2.1); ours is -1.2.
- Discounts make sense only when leftover stock would otherwise be wasted (clearance) - next lesson.

## Lesson 37 - Clearance markdowns (closes M6)
- 6 weeks left, elasticity -1.2, outlet pays 10% of full price; cost already spent so it doesn't matter.
- Rule: discount just enough to sell out on the last day; never deeper than 40% (below that, the outlet pays more than extra store sales).
- 9,320 items: 1,045 need 0%, 3,334 get 5-35%, 4,941 overstocked hit the 40% floor.
- Money: no discount 1,657,559 | flat 50% off 1,387,018 (-16.3%) | smart per-item 1,684,921 (+1.7%).
- Lesson: blanket sales destroy value; per-item markdowns beat flat by +21%. Gain vs no discount is small because elasticity is near -1.

## Lesson 38 - Forecast baselines (M7 starts)
- 104 full weeks (Sep 2018 - Sep 2020); last 8 weeks hidden as the test.
- WAPE: seasonal (same weeks last year) 8.4% | naive (last week) 10.0% | avg of last 4 weeks 13.0%.
- Fashion is seasonal; the 4-week average was inflated by the July summer sale.
- Bug caught: u32 columns wrap around on subtraction (782,410% WAPE) - always cast to float.
- Bar to beat for the ML forecaster: 8.4%.

## Lesson 39 - ML forecaster vs seasonal baseline
- Global LightGBM over 10 product groups (50k+ units), clues = lags 8-11, 52, 53 + week of year + group; only 430 training rows.
- Per group WAPE: seasonal 17.2% vs ML 16.9%. Company total: seasonal 8.4% vs ML 8.6% -> effectively a tie.
- ML is not magic: short history + COVID-distorted training year + 8-week gap = simple seasonal is hard to beat. Always show the baseline.
- Errors cancel when added up: 17% per group vs 8.4% total, so item/size-level stock decisions face much bigger uncertainty.

## Lesson 40 - Forecast ranges
- Goal: low (10th pct) / high (90th pct) so reality lands inside about 80% of the time.
- Quantile LightGBM: only 44% inside (width 42% of sales) = overconfident; also quantile crossing (low > mid for Shoes, 3 Aug).
- Past-miss range (seasonal x 10th/90th pct of past actual/last-year ratios = 0.59x to 1.87x): 88% inside, width 123%.
- Honest wide ranges beat narrow wrong ones; the width reflects real COVID-era volatility and should drive stock strategy.

## Lesson 41 - How much to order (closes M7)
- Newsvendor: running short costs 0.50 (lost margin), a leftover costs 0.40 (cost 0.50 - outlet 0.10) -> order at the 56% level of past misses (about 1.0x last year).
- Profit on 80 test group-weeks: perfect 1,096,230 | last year 926,044 (84%) | newsvendor 923,011 (84%) | order the 90th-pct high case 318,018 (29%).
- "Never run out" destroys profit (this is how Lesson 37 overstock happens).
- Price of uncertainty = 16% of profit (about 173k per 8 weeks) -> the business case for better forecasts.

## Lesson 42 - Recommender baseline (M8 starts)
- Time machine: history up to 15 Sep 2020; test week 16-22 Sep 2020 = 68,984 buyers (only 5% of customers shop in a given week).
- Popularity baseline: everyone gets the 12 bestsellers of 9-15 Sep -> hit rate 6.43% (1 in 16 buyers bought at least one).
- Strong cheap baseline (why homepages show bestsellers), but identical for every customer. Bar to beat: 6.43%.

## Lesson 43 - Buy-again recommender
- Candidates = each customer's own items from the last 4 weeks (most-bought, then most recent), bestsellers fill remaining slots.
- 235,277 customers had a purchase in the 4 weeks before the cut.
- Hit rate: popular only 6.43% | buy-again only 5.48% | buy-again + popular 10.65% (+66% vs baseline).
- Different sources catch different customers; real recommenders combine candidate sources.
