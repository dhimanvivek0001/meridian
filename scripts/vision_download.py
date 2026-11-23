# Lesson 46 (setup): download product images for the 3,000 top sellers before the cut - resumable, polite, skips missing
import shutil
import sys
import time
from pathlib import Path

import polars as pl
from kaggle.api.kaggle_api_extended import KaggleApi

COMP = "h-and-m-personalized-fashion-recommendations"
OUT, TMP = Path("data/images"), Path("data/images/_tmp")
PAUSE = 1.5  # seconds between requests; 0.6s triggered long runs of HTTP 429 (Too Many Requests)

# Optional: pass a parquet file with an article_id column to fetch a different list (Lesson 49: new test-week items)
if len(sys.argv) > 1:
    pick = pl.read_parquet(sys.argv[1]).select("article_id")
    print(f"Custom list: {pick.height:,} articles from {sys.argv[1]}")
else:
    pick = None

# Default (Lesson 46): top 3,000 articles by units sold in the 4 weeks BEFORE the 16 Sep cut (no test-week peeking)
pick = pick if pick is not None else (
    pl.scan_parquet("data/clean/transactions.parquet")
    .filter(pl.col("sale_date").is_between(pl.date(2020, 8, 19), pl.date(2020, 9, 15)))
    .group_by("article_id").agg(pl.len().alias("n"))
    .sort(["n", "article_id"], descending=[True, False]).head(3000)
    .collect()
)
if len(sys.argv) == 1:
    assert pick.height == 3000
    pick.write_parquet("data/clean/vision_articles.parquet")

api = KaggleApi()
api.authenticate()
missing_file = OUT / "missing.txt"
missing = set(missing_file.read_text().split()) if missing_file.exists() else set()
done = got = 0
start = time.time()
for i, a in enumerate(pick["article_id"].to_list(), 1):
    final = OUT / a[:3] / f"{a}.jpg"
    if (final.exists() and final.stat().st_size > 0) or a in missing:
        done += 1
        continue
    name = f"images/{a[:3]}/{a}.jpg"
    for attempt in range(6):
        try:
            if TMP.exists():
                shutil.rmtree(TMP)  # clear any half-written file from an earlier interrupted attempt
            api.competition_download_file(COMP, name, path=str(TMP), quiet=True)
            src = next(TMP.rglob(f"{a}.jpg"))
            final.parent.mkdir(parents=True, exist_ok=True)
            src.replace(final)  # move only once complete, so a crash never leaves a broken image behind
            got += 1
            break
        except Exception as e:
            msg = str(e)
            if "404" in msg or "Not Found" in msg:
                missing.add(a)
                missing_file.write_text("\n".join(sorted(missing)))
                break
            wait = 15 * 2**attempt if "429" in msg else 5
            print(f"  {a}: {type(e).__name__} {msg[:60]} - retry in {wait}s", flush=True)
            time.sleep(wait)
    else:
        print(f"  {a}: gave up after 6 tries (will retry on next run)", flush=True)
    time.sleep(PAUSE)
    if i % 100 == 0:
        print(f"{i:,}/3,000 checked | {got:,} new this run | {len(missing)} missing | {time.time() - start:.0f}s", flush=True)

files = list(OUT.glob("[0-9][0-9][0-9]/*.jpg"))
total = sum(f.stat().st_size for f in files)
print(f"DONE: {len(files):,} images on disk, {total / 1e6:.0f} MB; {len(missing)} articles have no image on Kaggle")
