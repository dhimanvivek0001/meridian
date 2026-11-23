# Lesson 54: MLflow experiment tracking - log the churn models (L16/L18/L19) and the L45 ranker with params, metrics, model files
import contextlib
import hashlib
import io
import os
import runpy
import subprocess
import time
from importlib.metadata import version
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
os.environ.setdefault("MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR", "false")
import mlflow
import numpy as np
import polars as pl
from lightgbm import LGBMClassifier, LGBMRanker
from mlflow.models import infer_signature
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 54
np.random.seed(SEED)
STORE = Path("data/mlflow")  # inside data/ = gitignored: runs and model files never reach the repo
STORE.mkdir(parents=True, exist_ok=True)
mlflow.set_tracking_uri(f"sqlite:///{STORE.as_posix()}/mlflow.db")


def experiment(name):
    """Create the experiment once, with its model files stored under data/mlflow/artifacts."""
    if mlflow.get_experiment_by_name(name) is None:
        mlflow.create_experiment(name, artifact_location=(STORE / "artifacts" / name).resolve().as_uri())
    mlflow.set_experiment(name)


def md5(path):
    """Fingerprint of a data file: if the data changes, the fingerprint changes (reproducibility)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


BATCH = time.strftime("%Y%m%d-%H%M%S")  # one id per script execution, so a re-run never mixes with older runs
# Exact packages the models need to be loaded again (otherwise MLflow guesses from everything imported, torch included)
REQS = [f"{p}=={version(p)}" for p in ["lightgbm", "scikit-learn", "numpy", "mlflow"]]
GIT = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
if subprocess.run(["git", "status", "--porcelain", "scripts"], capture_output=True, text=True).stdout.strip():
    GIT += "-dirty"  # code differs from the commit: the run can't be traced back exactly, so say so
print(f"Tracking store: {STORE}/mlflow.db | code version (git): {GIT}")

# ---------------- 1. Churn models (L16 logistic, L18 LightGBM, L19 v2 clues) ----------------
experiment("meridian-churn")
V1 = ["days_since", "visits", "spend", "items", "online_share"]
V2 = V1 + ["visits_4w", "visits_prev12w", "avg_gap", "overdue", "age", "FN", "club_active", "news_regular"]
LOGGED = {"days_since", "visits", "spend", "items", "visits_4w", "visits_prev12w", "avg_gap", "overdue"}
data = {
    "v1": (pl.read_parquet("data/clean/churn_train.parquet"), pl.read_parquet("data/clean/churn_test.parquet"), "data/clean/churn_train.parquet"),
    "v2": (pl.read_parquet("data/clean/churn_train_v2.parquet"), pl.read_parquet("data/clean/churn_test_v2.parquet"), "data/clean/churn_train_v2.parquet"),
}
assert data["v1"][0].height == 988_844 and data["v1"][1].height == 984_525


def churn_run(name, version, kind, params, lesson):
    train, test, path = data[version]
    names = V1 if version == "v1" else V2
    # logistic regression gets log-shrunk clues (L16); trees take raw clues (L18)
    cols = [pl.col(n).log1p() if (kind == "logreg" and n in LOGGED) else pl.col(n) for n in names]
    Xtr, Xte = train.select(cols).to_numpy(), test.select(cols).to_numpy()
    ytr, yte = train["churned"].to_numpy(), test["churned"].to_numpy()
    with mlflow.start_run(run_name=name):
        mlflow.set_tags({"lesson": lesson, "git_commit": GIT, "batch": BATCH, "model_type": kind, "features": version})
        mlflow.log_params({**params, "n_features": len(names), "train_rows": len(ytr), "test_rows": len(yte),
                           "train_data_md5": md5(path), "train_cutoff": "2020-06-02", "test_cutoff": "2020-07-28"})
        t0 = time.time()
        if kind == "logreg":
            model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, **params))
        else:
            model = LGBMClassifier(**params, random_state=42, verbose=-1)
        model.fit(Xtr, ytr)
        risk = model.predict_proba(Xte)[:, 1]
        top10 = yte[risk >= np.quantile(risk, 0.9)].mean()  # churn rate in the riskiest 10%
        metrics = {"auc": roc_auc_score(yte, risk), "accuracy": accuracy_score(yte, risk >= 0.5),
                   "log_loss": log_loss(yte, risk), "top10_churn_rate": top10, "lift_top10": top10 / yte.mean(),
                   "train_seconds": time.time() - t0}
        mlflow.log_metrics(metrics)
        if kind == "lightgbm":
            gain = model.booster_.feature_importance("gain")
            mlflow.log_dict({n: round(float(g / gain.sum()), 4) for n, g in sorted(zip(names, gain), key=lambda x: -x[1])},
                            "feature_importance.json")
            flavor = mlflow.lightgbm
        else:
            flavor = mlflow.sklearn
        sig = infer_signature(Xte[:100], risk[:100])
        flavor.log_model(model, name="model", signature=sig, input_example=Xte[:3], pip_requirements=REQS)
    print(f"  {name:34s} AUC {metrics['auc']:.3f}  acc {metrics['accuracy']:.1%}  top-10% churn {top10:.1%}  ({metrics['train_seconds']:.0f}s)")


print("\nChurn runs:")
churn_run("L16 logistic v1 (5 clues)", "v1", "logreg", {"C": 1.0}, "L16")
churn_run("L18 LightGBM v1 (5 clues)", "v1", "lightgbm", {"n_estimators": 300, "learning_rate": 0.05, "num_leaves": 31}, "L18")
churn_run("L19 logistic v2 (13 clues)", "v2", "logreg", {"C": 1.0}, "L19")
churn_run("L19 LightGBM v2 (13 clues)", "v2", "lightgbm", {"n_estimators": 300, "learning_rate": 0.05, "num_leaves": 31}, "L19")
churn_run("L54 LightGBM v2 small trees", "v2", "lightgbm", {"n_estimators": 600, "learning_rate": 0.05, "num_leaves": 15}, "L54")
churn_run("L54 LightGBM v2 big trees", "v2", "lightgbm", {"n_estimators": 300, "learning_rate": 0.1, "num_leaves": 127}, "L54")

# ---------------- 2. The L45 ranker: re-run the lesson script, then log it + 2 variants ----------------
experiment("meridian-reco-ranker")
print("\nRe-running scripts/reco_ranker.py (L45) to get its data and model (its own printout is hidden) ...")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    g = runpy.run_path("scripts/reco_ranker.py")
fit, groups, test, FEATURES, top12_hit = g["fit"], g["groups"], g["test"], g["FEATURES"], g["top12_hit"]
assert g["n_test"] == 68_984
TX_MD5 = md5("data/clean/transactions.parquet")


def ranker_run(name, model, lesson):
    with mlflow.start_run(run_name=name):
        mlflow.set_tags({"lesson": lesson, "git_commit": GIT, "batch": BATCH, "model_type": "lightgbm_lambdarank"})
        p = model.get_params()
        mlflow.log_params({k: p[k] for k in ["n_estimators", "learning_rate", "num_leaves", "min_child_samples",
                                             "subsample", "colsample_bytree", "random_state"]}
                          | {"train_rows": fit.height, "train_groups": len(groups), "n_features": len(FEATURES),
                             "transactions_md5": TX_MD5, "test_week": "2020-09-16..22"})
        t0 = time.time()
        if not hasattr(model, "booster_"):
            model.fit(fit.select(FEATURES).to_numpy(), fit["label"].to_numpy(), group=groups)
        secs = time.time() - t0
        X = test.select(FEATURES).to_numpy()
        hit = top12_hit(test.with_columns(pl.Series("s", model.predict(X))), "s")
        mlflow.log_metrics({"hit_rate_12": hit, "rule_hit_rate_12": g["rule"], "candidate_recall": g["recall"](test),
                            "gain_vs_L44": hit - 0.1137, "train_seconds": secs})
        gain = model.booster_.feature_importance("gain")
        mlflow.log_dict({n: round(float(v / gain.sum()), 4) for n, v in sorted(zip(FEATURES, gain), key=lambda x: -x[1])},
                        "feature_importance.json")
        # Log the native LightGBM booster (plain-text model file) - MLflow 3 refuses to pickle LGBMRanker as an "untrusted type"
        mlflow.lightgbm.log_model(model.booster_, name="model", signature=infer_signature(X[:100], model.predict(X[:100])),
                                  input_example=X[:3], pip_requirements=REQS)
    print(f"  {name:34s} hit@12 {hit:.2%}  (hand rule {g['rule']:.2%})")
    return hit


print("Ranker runs:")
base = g["model"].get_params()
ranker_run("L45 ranker (as published)", g["model"], "L45")  # already trained inside reco_ranker.py
ranker_run("L54 ranker 100 trees", LGBMRanker(**(base | {"n_estimators": 100})), "L54")
ranker_run("L54 ranker 63 leaves", LGBMRanker(**(base | {"num_leaves": 63})), "L54")

# Reproducibility check: every run of the PUBLISHED L45 ranker ever logged - same code + data should give the same result
hist = pl.from_pandas(mlflow.search_runs(experiment_names=["meridian-reco-ranker"],
                                         filter_string="tags.mlflow.runName = 'L45 ranker (as published)'", order_by=["start_time ASC"]))
print("\nAll logged runs of the published L45 ranker (same seed, same data):")
for b, gc, h in hist.select(["tags.batch", "tags.git_commit", "metrics.hit_rate_12"]).iter_rows():
    print(f"  batch {b or '(first, failed attempt)':24s} code {gc:14s} hit@12 {h:.4%} = {round(h * 68_984):,} buyers")

# ---------------- 3. Compare runs (what the MLflow UI shows, as a table) ----------------
for exp, metric in [("meridian-churn", "auc"), ("meridian-reco-ranker", "hit_rate_12")]:
    runs = pl.from_pandas(mlflow.search_runs(experiment_names=[exp], filter_string=f"tags.batch = '{BATCH}'",
                                            order_by=[f"metrics.{metric} DESC"]))
    keep = ["tags.mlflow.runName", f"metrics.{metric}", "params.n_estimators", "params.learning_rate", "params.num_leaves", "metrics.train_seconds"]
    print(f"\n{exp}: {runs.height} runs, best first")
    for r in runs.select([c for c in keep if c in runs.columns]).iter_rows():
        print("  " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v) for v in r))
print(f"\nOpen the UI:  .venv\\Scripts\\mlflow ui --backend-store-uri sqlite:///{STORE.as_posix()}/mlflow.db  -> http://127.0.0.1:5000")
