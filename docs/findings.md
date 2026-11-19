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
