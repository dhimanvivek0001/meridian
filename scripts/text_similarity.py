# Lesson 48: text similarity on detail_desc - TF-IDF baseline vs a sentence-embedding model (MiniLM)
import os
import time

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import numpy as np
import polars as pl
import torch
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

SEED = 48
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.set_num_threads(8)
T0 = time.time()
log = lambda msg: print(f"[{time.time() - T0:5.0f}s] {msg}", flush=True)

arts = pl.read_parquet("data/parquet/articles.parquet").filter(pl.col("detail_desc").is_not_null())
assert arts.height == 105542 - 416

# Colour variants share the SAME description, so keep one article per product (otherwise "nearest = same product")
one = arts.sort("article_id").unique("product_code", keep="first", maintain_order=True)
bench = one.sample(10_000, seed=SEED)
assert bench["product_code"].n_unique() == 10_000
texts = bench["detail_desc"].to_list()
log(f"Benchmark: {bench.height:,} products (one colour each), median {np.median([len(t.split()) for t in texts]):.0f} words")


def nearest(emb, codes=None, block=1000):
    """Index of each row's most similar other row, computed 1,000 rows at a time (never the full matrix).
    emb rows must have length 1 (then dot product = cosine similarity); works for dense or sparse."""
    n, out = emb.shape[0], np.empty(emb.shape[0], dtype=np.int64)
    for s in range(0, n, block):
        sim = emb[s:s + block] @ emb.T
        sim = sim.toarray() if hasattr(sim, "toarray") else np.asarray(sim)
        sim[np.arange(sim.shape[0]), np.arange(s, s + sim.shape[0])] = -np.inf  # not yourself
        if codes is not None:
            sim[codes[s:s + block, None] == codes[None, :]] = -np.inf  # not another colour of yourself
        out[s:s + block] = sim.argmax(axis=1)
    return out


def embed_minilm(t):
    m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    return m.encode(t, batch_size=128, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)


# CLIP's text encoder was dropped: it took ~15 min on this CPU for 80.5% same-type vs MiniLM's 80.1% in ~2 min (see L48.md)


cols = ["product_type_name", "colour_group_name", "department_name"]


def score(nn, meta):
    return {c: (meta[c].to_numpy()[nn] == meta[c].to_numpy()).mean() for c in cols}


chance = {c: (bench[c].value_counts(normalize=True)["proportion"].to_numpy() ** 2).sum() for c in cols}
results, nns = {}, {}

tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, stop_words="english")
X = tfidf.fit_transform(texts).astype(np.float32)  # rows already have length 1 (TF-IDF normalises)
log(f"TF-IDF vocabulary: {len(tfidf.vocabulary_):,} words/word-pairs")
nns["TF-IDF (word counts)"] = nearest(X)
log("TF-IDF neighbours done")
nns["MiniLM sentence model"] = nearest(embed_minilm(texts))
log("MiniLM neighbours done")

print("\nNearest neighbour shares the same...      type    colour  department")
print(f"  {'Random pair (chance)':30s}       {chance[cols[0]]:6.1%}  {chance[cols[1]]:6.1%}  {chance[cols[2]]:6.1%}")
for name, nn in nns.items():
    r = score(nn, bench)
    print(f"  {name:30s}       {r[cols[0]]:6.1%}  {r[cols[1]]:6.1%}  {r[cols[2]]:6.1%}")

# Show where methods disagree, on one random product
i = int(np.random.default_rng(SEED).integers(len(texts)))
print(f"\nExample: [{bench['product_type_name'][i]}] {texts[i][:110]}")
for name, nn in nns.items():
    j = int(nn[i])  # polars needs a plain Python int, not numpy.int64
    print(f"  {name:22s} -> [{bench['product_type_name'][j]}] {texts[j][:90]}")

# Text vs photo on the 1,935 photographed items (L46); other colours of the same product are not allowed as neighbours
img = pl.read_parquet("data/clean/image_embeddings.parquet")
photo = img.select("article_id").join(arts, on="article_id", how="left")
assert photo.height == img.height and photo["detail_desc"].null_count() == 0
codes = photo["product_code"].to_numpy()
im = img["emb"].to_numpy().astype(np.float32)
tx_emb = embed_minilm(photo["detail_desc"].to_list())
both = np.hstack([im, tx_emb]) / np.sqrt(2)  # glue the two lists together; length stays 1
print(f"\nPhoto items ({photo.height:,}), other colours of the same product excluded as neighbours:")
print("                                type    colour  department")
for name, e in [("Image (CLIP photo)", im), ("Text (MiniLM)", tx_emb), ("Image + text", both)]:
    r = score(nearest(e, codes), photo)
    print(f"  {name:28s}  {r[cols[0]]:6.1%}  {r[cols[1]]:6.1%}  {r[cols[2]]:6.1%}")
log("done")
