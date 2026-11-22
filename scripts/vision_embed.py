# Lesson 46: turn product photos into CLIP embeddings (512 numbers each) on CPU, then check they make sense
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")  # harmless Windows cache warning

import numpy as np
import open_clip
import polars as pl
import torch
from PIL import Image

SEED = 46
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.set_num_threads(8)

# 1. Which of the 3,000 picked articles actually have a photo on disk?
pick = pl.read_parquet("data/clean/vision_articles.parquet")
assert pick.height == 3000
pick = pick.with_columns(
    pl.col("article_id").map_elements(lambda a: f"data/images/{a[:3]}/{a}.jpg", return_dtype=pl.String).alias("path")
)
pick = pick.filter(pl.col("path").map_elements(lambda p: Path(p).exists(), return_dtype=pl.Boolean))
print(f"Articles with a photo: {pick.height:,} of 3,000")

# 2. Load CLIP ViT-B/32 (OpenAI weights) - downloaded once, then cached
# "-quickgelu" matches how OpenAI trained these weights (plain "ViT-B-32" warns of a QuickGELU mismatch)
model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32-quickgelu", pretrained="openai")
tokenizer = open_clip.get_tokenizer("ViT-B-32-quickgelu")
model.eval()

# 3. Embed in batches of 64 photos
paths, vecs = pick["path"].to_list(), []
with torch.no_grad():
    for i in range(0, len(paths), 64):
        batch = torch.stack([preprocess(Image.open(p).convert("RGB")) for p in paths[i:i + 64]])
        v = model.encode_image(batch)
        vecs.append((v / v.norm(dim=-1, keepdim=True)).numpy())  # length 1, so dot product = cosine similarity
        if (i // 64) % 10 == 0:
            print(f"  embedded {min(i + 64, len(paths)):,}/{len(paths):,}", flush=True)
emb = np.vstack(vecs).astype(np.float32)
assert emb.shape == (pick.height, 512)
print(f"Embedding matrix: {emb.shape[0]:,} photos x {emb.shape[1]} numbers")

# 4. Similarity of every photo to every other photo; ignore an item's similarity to itself
sim = emb @ emb.T
np.fill_diagonal(sim, -1)
nn = np.argsort(-sim, axis=1)[:, :5]  # 5 most similar photos per item

# 5. Sanity check: do visual neighbours share product type / colour more often than chance?
arts = pl.read_parquet("data/parquet/articles.parquet").select(
    ["article_id", "prod_name", "product_type_name", "colour_group_name"]
)
meta = pick.select("article_id").join(arts, on="article_id", how="left")
assert meta.height == pick.height
for col in ["product_type_name", "colour_group_name"]:
    v = meta[col].to_numpy()
    same_nn = (v[nn[:, 0]] == v).mean()
    share = meta[col].value_counts(normalize=True)["proportion"].to_numpy()
    chance = (share ** 2).sum()  # chance two random items match
    print(f"Nearest neighbour has same {col:18s}: {same_nn:.1%}  (random pair: {chance:.1%})")

# 6. Show a few examples: item -> its 3 closest photos
rng = np.random.default_rng(SEED)
names = meta["prod_name"].to_list()
types = meta["product_type_name"].to_list()
print("\nExamples (similarity in brackets):")
for i in rng.choice(len(names), 4, replace=False):
    near = ", ".join(f"{names[j]} [{sim[i, j]:.2f}]" for j in nn[i, :3])
    print(f"  {names[i]} ({types[i]}) -> {near}")

# 7. Bonus: CLIP also understands text - search the photos with words
with torch.no_grad():
    for q in ["a photo of a red dress", "a photo of black jeans", "a photo of a striped sweater"]:
        t = model.encode_text(tokenizer([q]))
        t = (t / t.norm(dim=-1, keepdim=True)).numpy()[0]
        top = np.argsort(-(emb @ t))[:3]
        print(f"  '{q}' -> " + ", ".join(f"{names[j]} ({types[j]})" for j in top))

pl.DataFrame({"article_id": pick["article_id"], "emb": emb}).write_parquet("data/clean/image_embeddings.parquet")
print("Saved data/clean/image_embeddings.parquet")
