# Reverse ETL: send each audience file to the ad platform API in batches of 10,000
import polars as pl
import requests
from pathlib import Path

API = "http://127.0.0.1:8000"
BATCH = 10000

for f in sorted(Path("data/exports").glob("*.csv")):
    df = pl.read_csv(f)
    names = df["audience"].unique().to_list()
    assert len(names) == 1, f"{f.name} contains more than one audience"
    name = names[0]                      # audience name from INSIDE the file, not the file name
    ids = df["external_id"].to_list()

    for start in range(0, len(ids), BATCH):
        chunk = ids[start:start + BATCH]
        r = requests.post(f"{API}/audiences/{name}/members", json={"external_ids": chunk}, timeout=30)
        r.raise_for_status()             # stop loudly if the platform says no

    batches = (len(ids) + BATCH - 1) // BATCH
    print(f"{name}: sent {len(ids)} in {batches} batches -> platform total {r.json()['total']}")

print("Platform now holds:", requests.get(f"{API}/audiences").json())