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

