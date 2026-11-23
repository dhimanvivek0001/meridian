# Lesson 49: cold start - which brand-new items (no sales history) will each customer buy? Text + photo vs simple rules
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import numpy as np
import open_clip
import polars as pl
import torch
from PIL import Image
from sentence_transformers import SentenceTransformer

SEED = 49
rng = np.random.default_rng(SEED)
torch.manual_seed(SEED)
torch.set_num_threads(8)
tx = pl.scan_parquet("data/clean/transactions.parquet")
arts = pl.read_parquet("data/parquet/articles.parquet")
CUT = pl.date(2020, 9, 16)

# 1. The new items: first ever sale in the test week (the retailer knows its launch list in advance)
new = pl.read_parquet("data/clean/new_items.parquet").join(arts, on="article_id", how="left")
assert new.height == 667
test = tx.filter(pl.col("sale_date") >= CUT).select(["customer_id", "article_id"]).unique().collect()
hist = (
    tx.filter(pl.col("sale_date").is_between(pl.date(2020, 8, 19), pl.date(2020, 9, 15)))
    .select(["customer_id", "article_id"]).collect()
    .join(arts.select(["article_id", "product_code", "product_type_name", "detail_desc"]), on="article_id", how="left")
)
# Customers to score: test buyers WITH 4-week history who bought at least one new item
bought_new = test.join(new.select("article_id"), on="article_id")
custs = bought_new.select("customer_id").unique().join(hist.select("customer_id").unique(), on="customer_id").sort("customer_id")
assert custs.height == 2920
hist = hist.join(custs, on="customer_id")
C, N = custs.height, new.height
cidx = {c: i for i, c in enumerate(custs["customer_id"])}
nidx = {a: j for j, a in enumerate(new["article_id"])}
print(f"New items: {N} ({new['product_code'].is_in(hist['product_code'].implode()).sum()} share a product with something a scored customer owns)")
print(f"Customers scored: {C:,} | their 4-week history: {hist.height:,} lines")

truth = np.zeros((C, N), dtype=bool)
for c, a in bought_new.join(custs, on="customer_id").iter_rows():
    truth[cidx[c], nidx[a]] = True
print(f"New items bought per scored customer: {truth.sum(1).mean():.2f}")


def hit12(score, name, t=None):
    """Top 12 new items per customer; hit = bought at least one. Tiny noise breaks ties fairly.
    t = the truth matrix to use (default: all scored customers x all 667 new items)."""
    t = truth if t is None else t
    s = score + rng.uniform(0, 1e-6, score.shape)
    top = np.argpartition(-s, 12, axis=1)[:, :12]
    hit = t[np.arange(t.shape[0])[:, None], top].any(axis=1).mean()
    print(f"  {name:44s} {hit:6.2%}")
    return hit


def max_sim(owner_rows, own_emb, new_emb):
    """For each customer: highest similarity between any of their own items and each new item."""
    out = np.full((C, N), np.nan, dtype=np.float32)
    sims = own_emb @ new_emb.T
    for i in np.unique(owner_rows):
        out[i] = sims[owner_rows == i].max(axis=0)
    return out


# 2. Simple baselines
res = {}
print("\nHit rate: one of 12 new-item picks was bought (customers who bought a new item):")
res["random"] = hit12(np.zeros((C, N)), "Random 12 new items")

types = sorted(set(new["product_type_name"]) | set(hist["product_type_name"]))
tix = {t: k for k, t in enumerate(types)}
last_week = tx.filter(pl.col("sale_date").is_between(pl.date(2020, 9, 9), pl.date(2020, 9, 15))).select("article_id").collect()
type_pop = last_week.join(arts.select(["article_id", "product_type_name"]), on="article_id")["product_type_name"].value_counts()
pop_vec = np.zeros(len(types))
for t, n in type_pop.iter_rows():
    if t in tix:
        pop_vec[tix[t]] = n
item_type = np.array([tix[t] for t in new["product_type_name"]])
res["type_pop"] = hit12(np.tile(pop_vec[item_type], (C, 1)), "Popular product types (same for everyone)")

aff = np.zeros((C, len(types)))
for c, t in hist.select(["customer_id", "product_type_name"]).iter_rows():
    aff[cidx[c], tix[t]] += 1
aff /= aff.sum(1, keepdims=True)
type_score = aff[:, item_type] + 1e-3 * pop_vec[item_type] / pop_vec.max()
res["aff"] = hit12(type_score, "Your product types (share of your purchases)")

same = np.zeros((C, N))
code_to_items = {}
for j, pc in enumerate(new["product_code"]):
    code_to_items.setdefault(pc, []).append(j)
for c, pc in hist.select(["customer_id", "product_code"]).unique().iter_rows():
    for j in code_to_items.get(pc, []):
        same[cidx[c], j] = 1
print(f"  (customers owning another colour of at least one new item: {(same.sum(1) > 0).mean():.1%})")
rules = same + type_score
res["rules"] = hit12(rules, "Rules: same product in new colour > your types")

# 3. Text: MiniLM on descriptions (embed each distinct description once)
mini = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
descs = sorted(set(hist["detail_desc"].drop_nulls()) | set(new["detail_desc"].drop_nulls()))
dvec = dict(zip(descs, mini.encode(descs, batch_size=128, normalize_embeddings=True, show_progress_bar=False)))
print(f"\n  Embedded {len(descs):,} distinct descriptions")
zero = np.zeros(384, dtype=np.float32)
new_txt = np.stack([dvec.get(d, zero) for d in new["detail_desc"].fill_null("")])
h_txt = hist.filter(pl.col("detail_desc").is_not_null())
txt_sim = max_sim(np.array([cidx[c] for c in h_txt["customer_id"]]), np.stack([dvec[d] for d in h_txt["detail_desc"]]), new_txt)
txt_sim = np.nan_to_num(txt_sim, nan=0.0)
res["text"] = hit12(txt_sim, "Text: closest to anything you bought (MiniLM)")

# 4. Photos: CLIP on new items (just downloaded) and owned items (L46 top-seller photos)
paths = [f"data/images/{a[:3]}/{a}.jpg" for a in new["article_id"]]
has_photo = np.array([Path(p).exists() for p in paths])
model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32-quickgelu", pretrained="openai")
model.eval()
new_img = np.zeros((N, 512), dtype=np.float32)
with torch.no_grad():
    idx = np.flatnonzero(has_photo)
    for s in range(0, len(idx), 64):
        b = idx[s:s + 64]
        v = model.encode_image(torch.stack([preprocess(Image.open(paths[j]).convert("RGB")) for j in b]))
        new_img[b] = (v / v.norm(dim=-1, keepdim=True)).numpy()
old = pl.read_parquet("data/clean/image_embeddings.parquet")
h_img = hist.join(old.with_row_index("r"), on="article_id")
img_sim = max_sim(np.array([cidx[c] for c in h_img["customer_id"]]), old["emb"].to_numpy()[h_img["r"].to_numpy()], new_img)
cover = ~np.isnan(img_sim).all(1)
print(f"  New items with a photo: {has_photo.sum()} of {N} | customers with an owned photo: {cover.mean():.1%}")
img_sim = np.nan_to_num(img_sim, nan=0.0)
img_sim[:, ~has_photo] = 0.0
res["image"] = hit12(img_sim, "Photo: closest to anything you bought (CLIP)")

z = lambda s: (s - s.mean()) / s.std()
both = np.where(cover[:, None] & has_photo[None, :], (z(txt_sim) + z(img_sim)) / 2, z(txt_sim))
res["both"] = hit12(both, "Text + photo (photo only where available)")
res["rules_text"] = hit12(same * 10 + z(txt_sim), "Rules (same product) + text for the rest")

# 5. Fair photo test: only the new items that HAVE a photo, only customers who bought one and own a photographed item
rows_ok = cover & truth[:, has_photo].any(1)
sub = np.ix_(rows_ok, has_photo)
t_sub = truth[sub]
print(f"\nLike-for-like on the {has_photo.sum()} photographed new items ({rows_ok.sum():,} customers):")
hit12(np.zeros(t_sub.shape), "Random 12", t_sub)
hit12(type_score[sub], "Your product types", t_sub)
hit12(txt_sim[sub], "Text (MiniLM)", t_sub)
hit12(img_sim[sub], "Photo (CLIP)", t_sub)
hit12(((z(txt_sim) + z(img_sim)) / 2)[sub], "Text + photo", t_sub)

# 6. Where do the hits come from? new colours vs truly new products
is_new_colour = same.any(0)
for label, mask in [("new colour of a product someone owns", is_new_colour), ("everything else", ~is_new_colour)]:
    print(f"  Purchases of {label}: {truth[:, mask].sum():,}")
print(f"\nBest vs random: {max(res.values()) / res['random']:.1f}x")
np.save("data/clean/new_items_text_emb.npy", new_txt)
