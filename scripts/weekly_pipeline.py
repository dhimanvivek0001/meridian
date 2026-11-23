# Lesson 55: reproducible weekly batch pipeline - data checks -> features -> drift check (PSI) -> champion churn model -> audiences
# Usage: .venv\Scripts\python scripts\weekly_pipeline.py [cutoff YYYY-MM-DD]   (default 2020-09-23 = day after the last sale)
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
os.environ.setdefault("MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR", "false")
sys.path.insert(0, str(Path(__file__).parent))
import mlflow
import numpy as np
import polars as pl
from mlflow import MlflowClient

from churn_data_v2 import make_features  # the SAME feature code the model was trained with (no copy-paste drift)

SEED = 55
np.random.seed(SEED)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
CUTOFF = date.fromisoformat(args[0]) if args else date(2020, 9, 23)
DRILL = "--drill" in sys.argv  # fire drill: simulate an upstream bug to prove the drift alarm works
OUT = Path(f"data/clean/weekly/{CUTOFF}{'-drill' if DRILL else ''}")
MODEL = "meridian-churn"
FEATURES = ["days_since", "visits", "spend", "items", "online_share", "visits_4w", "visits_prev12w",
            "avg_gap", "overdue", "age", "FN", "club_active", "news_regular"]
# Business rules for audiences (L17 corrected to margin in L51)
SAVE_RATE, MARGIN, VOUCHER_COST = 0.20, 0.50, 0.02
mlflow.set_tracking_uri("sqlite:///data/mlflow/mlflow.db")
client = MlflowClient()
print(f"=== Weekly pipeline for cutoff {CUTOFF} ===")

# ---------------- 1. Data checks: stop BEFORE scoring if the input looks wrong ----------------
tx = pl.scan_parquet("data/clean/transactions.parquet")
week = tx.filter(pl.col("sale_date").is_between(pl.lit(CUTOFF - timedelta(days=7)), pl.lit(CUTOFF - timedelta(days=1))))
prev8 = (tx.filter(pl.col("sale_date").is_between(pl.lit(CUTOFF - timedelta(days=63)), pl.lit(CUTOFF - timedelta(days=8))))
         .group_by(pl.col("sale_date").dt.truncate("1w")).agg(pl.len().alias("n")))
s = tx.select(
    pl.len().alias("rows"), pl.col("sale_date").max().alias("max_date"),
    *[pl.col(c).null_count().alias(f"null_{c}") for c in ["customer_id", "article_id", "sale_date", "price_index", "sales_channel"]],
    ((pl.col("price_index") <= 0) | (pl.col("price_index") >= 1)).sum().alias("bad_price"),
    (~pl.col("sales_channel").is_in(["online", "store"])).sum().alias("bad_channel"),
).collect().row(0, named=True)
week_rows = week.select(pl.len()).collect().item()
usual = prev8.collect()["n"].median() or 0
custs = pl.read_parquet("data/clean/customers.parquet").select("customer_id")
missing_cust = week.select("customer_id").unique().join(custs.lazy(), on="customer_id", how="anti").select(pl.len()).collect().item()
# HARD checks stop the run (the data is broken or stale). SOFT checks only warn: a sale week legitimately doubles
# volume (Easter 2020, the 28 Sep 2019 spike from L52), and stopping the weekly scoring for that would be wrong.
checks = [  # (name, passed, detail, hard?)
    ("data is fresh (last sale = day before cutoff)", s["max_date"] >= CUTOFF - timedelta(days=1), f"last sale {s['max_date']}", True),
    ("last week's volume within 50-150% of usual", usual > 0 and 0.5 <= week_rows / usual <= 1.5, f"{week_rows:,} rows vs usual {usual:,.0f}", False),
    ("no nulls in key columns", sum(v for k, v in s.items() if k.startswith("null_")) == 0, "5 columns checked", True),
    ("prices between 0 and 1", s["bad_price"] == 0, f"{s['bad_price']} bad", True),
    ("channel is online/store", s["bad_channel"] == 0, f"{s['bad_channel']} bad", True),
    ("customer ids unique in customers table", custs.height == custs["customer_id"].n_unique(), f"{custs.height:,} rows", True),
    ("every buyer exists in customers table", missing_cust == 0, f"{missing_cust} missing", True),
]
print("\n1. Data checks")
for name, ok, detail, hard in checks:
    print(f"  [{'PASS' if ok else 'FAIL' if hard else 'WARN'}] {name:45s} {detail}")
failed = [n for n, ok, _, hard in checks if not ok and hard]
warned = [n for n, ok, _, hard in checks if not ok and not hard]
if failed:
    sys.exit(f"STOPPED: {len(failed)} hard data check(s) failed - nothing was scored or written")

# ---------------- 2. Features (same code as training) ----------------
# Round floats to 9 decimals: multi-threaded sums can differ in the 14th decimal between runs, which can flip a
# customer sitting exactly on a rule boundary - rounding makes the output identical run after run
feat = make_features(CUTOFF).collect().sort("customer_id").with_columns(pl.col(pl.Float64).round(9))
assert feat["customer_id"].n_unique() == feat.height and feat.select(FEATURES).null_count().sum_horizontal().item() == 0
if DRILL:  # typical upstream bugs: a share arrives as a percentage (x100) and an age column shifted by 10 years
    feat = feat.with_columns(pl.col("online_share") * 100, pl.col("age") + 10)
    print("   DRILL MODE: online_share x100 and age +10 injected on purpose")
print(f"\n2. Features: {feat.height:,} customers who bought in the 12 months before {CUTOFF}")

# ---------------- 3. Champion model from the registry (register the best L54 run the first time) ----------------
if not [m for m in client.search_registered_models(f"name = '{MODEL}'")]:
    best = mlflow.search_runs(experiment_names=["meridian-churn"], filter_string="tags.features = 'v2' and tags.model_type = 'lightgbm'",
                              order_by=["metrics.auc DESC"], max_results=1).iloc[0]
    v = mlflow.register_model(f"runs:/{best.run_id}/model", MODEL)
    client.set_registered_model_alias(MODEL, "champion", v.version)
    client.set_model_version_tag(MODEL, v.version, "features", ",".join(FEATURES))
    print(f"\n   Registered '{best['tags.mlflow.runName']}' (AUC {best['metrics.auc']:.4f}) as {MODEL} v{v.version} @champion")
champ = client.get_model_version_by_alias(MODEL, "champion")
assert champ.tags["features"] == ",".join(FEATURES), "champion was trained on different features"
model = mlflow.lightgbm.load_model(f"models:/{MODEL}@champion")
train_run = client.get_run(champ.run_id)
print(f"3. Champion: {MODEL} v{champ.version} = '{train_run.data.tags['mlflow.runName']}' (test AUC {train_run.data.metrics['auc']:.4f})")

# ---------------- 4. Drift check: PSI of each feature, this week vs the training data ----------------
def psi(ref, cur, bins=10):
    """Population Stability Index: <0.1 stable, 0.1-0.2 some shift, >0.2 big shift (rule of thumb)."""
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(ref, edges)[0] / len(ref)
    c = np.histogram(cur, edges)[0] / len(cur)
    r, c = np.clip(r, 1e-4, None), np.clip(c, 1e-4, None)  # avoid log(0)
    return float(((c - r) * np.log(c / r)).sum())


ref = pl.read_parquet("data/clean/churn_train_v2.parquet")
ref_risk = model.predict_proba(ref.select(FEATURES).to_numpy())[:, 1]
risk = model.predict_proba(feat.select(FEATURES).to_numpy())[:, 1]
drift = {f: psi(ref[f].to_numpy(), feat[f].to_numpy()) for f in FEATURES} | {"PREDICTED RISK": psi(ref_risk, risk)}
print("\n4. Drift vs training data (cutoff 2020-06-02), PSI:")
for f, v in sorted(drift.items(), key=lambda x: -x[1]):
    flag = "WARN big shift" if v > 0.2 else "note: some shift" if v > 0.1 else "ok"
    print(f"  {f:16s} {v:6.3f}  {flag}")
warn = [f for f, v in drift.items() if v > 0.2]
if warn:
    print(f"  WARNING: {len(warn)} feature(s) shifted a lot ({', '.join(warn)}). Scores are still written, but check before acting.")

# ---------------- 5. Score + audiences ----------------
scores = feat.select("customer_id", "spend").with_columns(pl.Series("risk", risk))
value = pl.col("risk") * SAVE_RATE * pl.col("spend") * MARGIN - VOUCHER_COST
spend_top10 = scores["spend"].quantile(0.9)
aud = scores.with_columns(
    pl.when(value > 0).then(pl.lit("winback_voucher"))
    .when(pl.col("risk") >= 0.5).then(pl.lit("reactivation_email"))
    .when((pl.col("risk") < 0.3) & (pl.col("spend") >= spend_top10)).then(pl.lit("vip_early_access"))
    .otherwise(pl.lit("no_action")).alias("audience")
)
assert aud.height == feat.height and aud["customer_id"].n_unique() == aud.height  # everyone exactly once
sizes = dict(aud["audience"].value_counts().sort("audience").iter_rows())
print(f"\n5. Scored {aud.height:,} customers (mean risk {risk.mean():.1%}). Audiences:")
for a, n in sizes.items():
    print(f"  {a:20s} {n:9,}")

OUT.mkdir(parents=True, exist_ok=True)
aud.select("customer_id", pl.col("risk").round(6), "audience").write_parquet(OUT / "audiences.parquet")
digest = hashlib.md5(aud.select("customer_id", pl.col("risk").round(6), "audience").write_csv().encode()).hexdigest()[:12]
(OUT / "report.json").write_text(json.dumps({"cutoff": str(CUTOFF), "model_version": champ.version, "checks": {n: bool(ok) for n, ok, *_ in checks},
                                             "psi": {k: round(v, 4) for k, v in drift.items()}, "audiences": sizes, "output_md5": digest}, indent=2))
print(f"  written to {OUT}/ (output fingerprint {digest})")

# ---------------- 6. Log the pipeline run itself ----------------
# Create the experiment with its files under data/mlflow (gitignored). A bare set_experiment() would store them in
# ./mlruns in the repo folder - which our first version did (experiment "meridian-weekly-pipeline").
EXP = "meridian-weekly"
if mlflow.get_experiment_by_name(EXP) is None:
    mlflow.create_experiment(EXP, artifact_location=Path(f"data/mlflow/artifacts/{EXP}").resolve().as_uri())
mlflow.set_experiment(EXP)
with mlflow.start_run(run_name=f"weekly {CUTOFF}{' DRILL' if DRILL else ''}"):
    mlflow.log_params({"cutoff": str(CUTOFF), "model": f"{MODEL} v{champ.version}", "customers": feat.height})
    mlflow.log_metrics({"psi_max": max(drift.values()), "psi_risk": drift["PREDICTED RISK"], "mean_risk": float(risk.mean()),
                        "checks_failed": len(failed), "checks_warned": len(warned), "features_drifted": len(warn)} | {f"aud_{a}": n for a, n in sizes.items()})
    mlflow.set_tag("output_md5", digest)
    mlflow.log_artifact(str(OUT / "report.json"))
print(f"6. Logged to MLflow experiment '{EXP}'")
