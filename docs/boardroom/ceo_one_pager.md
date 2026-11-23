# Meridian: what to do next (CEO one-pager)

*Data: 2 years of transactions, Sep 2018 to Sep 2020. € figures use stated assumptions (1 price unit = €590, 50% gross margin). They are illustrative, but every figure is consistent with every other.*

## The situation in one line

Revenue fell from **€271.0m to €246.6m (−9.0%)** and contribution fell from **€118.1m to €105.9m (−€12.2m)**. The decline **started before COVID** (−11% in Oct–Feb), so it is a product and customer problem, not only a lockdown problem.

## Five problems, ranked by money

| # | Problem | € at stake / yr | What we do on Monday | Owner |
|---|---|---|---|---|
| 1 | **Ordering for "never run out"** (always buying the high case) | **−€65m** if adopted | Order at the newsvendor level (about 1.0× last year). Never order to the 90th-percentile case. | Buying |
| 2 | **Shrinking sales**: tops and trousers = 92% of the pre-COVID loss. T-shirts −31%, mostly because we sold **20% fewer designs**. Online (69% of items) shrank fastest. | **−€12.2m** contribution already lost | Restore the T-shirt range (a buying decision we control). Work on online basket size. Test both before scaling. | Buying, eCom |
| 3 | **Blanket clearance sales** (flat 50% off) | **−€9.8m** if adopted | Discount per item, by sell-through: **+€0.94m**. Rule: 10% off only pays when sales rise 25%+, and our randomised test showed +14%. | Merch |
| 4 | **Win-back vouchers sent to everyone** | **+€2.75m** available | Send vouchers only where expected margin > cost (265k customers, not 985k). Next step: target by *uplift* for ~20% more saves per voucher. | CRM |
| 5 | **Marketing budget split** | **+€0.36m** proven (model claimed €9.40m) | Move ~20% of the suggested shift toward search and email, run a geo lift test, then move more. | Marketing |

**Total model value: €3.73m a year (3.0% of gross margin).** The bigger win is **avoiding the two bad policies**: −€9.8m and −€65m.

## Three things to watch

- **Forecast uncertainty costs up to €18.7m a year** (upper bound for a perfect forecast). Better forecasting is worth funding. Our honest ranges are wide, which is correct for COVID-era demand.
- **Loss prevention:** 5,406 sales at exactly 80% off, across 4,888 customers. That looks like a till-level discount scheme. Investigate it first.
- **Consent is the bottleneck:** only 36% of target customers can be emailed. Growing opt-in may beat any model upgrade.

## What is already running

The weekly churn scoring job runs on Databricks: bronze → silver → gold → scoring in **190 s**. It has data checks, drift monitoring and a registered champion model, and its audiences match the laptop version within 0.02%.

## What I would *not* do

- Trust a regression for pricing: it got the sign wrong (+0.14). Only a **randomised test** found the true elasticity (−1.2).
- Trust an optimizer's promise: the MMM over-promised **26×**.
- Fund a fancier recommender ranker: simple rules reach 11.42%, and the ML ranker adds 0.12 pts (11.54%), which is about the size of run-to-run noise. Better *candidates* matter more than ordering (ceiling 23.96%).
