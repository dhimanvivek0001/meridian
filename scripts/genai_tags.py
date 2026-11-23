# Lesson 50: GenAI - write short product tags + a one-line summary with a FREE local model (SmolLM2-360M, CPU, no API)
import os
import re
import time

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import numpy as np
import polars as pl
import torch
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import AutoModelForCausalLM, AutoTokenizer

SEED = 50
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.set_num_threads(8)
MODEL = "HuggingFaceTB/SmolLM2-360M-Instruct"  # 727 MB download, Apache-2.0 licence
N = 100  # ~19 s per item on CPU (two short generations), so 100 items take ~30 min
CACHE = "data/clean/genai_raw.parquet"  # generated text is saved, so a crash later never costs a re-run

# 1. Sample: 100 of the NEW test-week items (L49), one colour per product - the items a shop would need tags for
arts = pl.read_parquet("data/parquet/articles.parquet")
new = pl.read_parquet("data/clean/new_items.parquet").join(arts, on="article_id", how="left")
pool = new.filter(pl.col("detail_desc").is_not_null()).sort("article_id").unique("product_code", keep="first", maintain_order=True)
items = pool.sample(N, seed=SEED)
assert items.height == N and items["product_code"].n_unique() == N
print(f"New items: {new.height} | with a description, one per product: {pool.height} | sampled: {N}")

# 2. Baseline (no AI): the 5 highest TF-IDF words of each description, learned over all 105k descriptions
corpus = arts["detail_desc"].drop_nulls().unique().sort().to_list()
tfidf = TfidfVectorizer(stop_words="english", min_df=2, token_pattern=r"[a-zA-Z]{3,}").fit(corpus)
vocab = np.array(tfidf.get_feature_names_out())
X = tfidf.transform(items["detail_desc"].to_list())
base_tags = [", ".join(vocab[X[i].indices[np.argsort(-X[i].data)][:5]]) for i in range(N)]

# 3. The local language model: greedy decoding (no randomness) so every run gives the same text
tok = AutoTokenizer.from_pretrained(MODEL)
lm = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
lm.eval()
print(f"Model: {MODEL} ({sum(p.numel() for p in lm.parameters()) / 1e6:.0f}M parameters)")


# A 360M model can't follow a two-part "Tags: ... Summary: ..." format (first try: 0% usable).
# What works: ONE simple task per prompt + one worked example (a made-up product, "few-shot") + short outputs.
EX_IN = "Product: Shorts (Light Blue). Description: Shorts in washed denim with a high waist, zip fly and raw-edge hems."
TASKS = {  # task: (instruction, example answer, max new tokens)
    "tags": ("Give 5 short lowercase shopping tags for the product, comma separated. Only use facts from the description.",
             "denim, shorts, high waist, light blue, raw edge", 25),
    "summary": ("Write one catchy sentence (at most 15 words) to sell the product. Only use facts from the description.",
                "Light blue high-waisted denim shorts with raw-edge hems for easy summer style.", 35),
}


def generate(task, r):
    inst, ex_out, max_new = TASKS[task]
    q = f"Product: {r['product_type_name']} ({r['colour_group_name']}). Description: {r['detail_desc']}"
    chat = [{"role": "system", "content": inst}, {"role": "user", "content": EX_IN},
            {"role": "assistant", "content": ex_out}, {"role": "user", "content": q}]
    ids = tok(tok.apply_chat_template(chat, tokenize=False, add_generation_prompt=True), return_tensors="pt")
    # no_repeat_ngram_size=3: greedy decoding can loop ("V-neck, V-neck, V-neck..."); this bans repeating any 3-token phrase
    gen = lm.generate(**ids, max_new_tokens=max_new, do_sample=False, no_repeat_ngram_size=3, pad_token_id=tok.eos_token_id)
    return tok.decode(gen[0, ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()


rows = list(items.iter_rows(named=True))
if os.path.exists(CACHE) and pl.read_parquet(CACHE)["article_id"].to_list() == items["article_id"].to_list():
    raw = pl.read_parquet(CACHE)
    secs = raw["secs"][0]
    print("Re-using saved generations from", CACHE)
else:
    raw_tags, raw_sum, t0 = [], [], time.time()
    with torch.no_grad():
        for i, r in enumerate(rows):
            raw_tags.append(generate("tags", r))
            raw_sum.append(generate("summary", r))
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{N} generated | {(time.time() - t0) / (i + 1):.1f}s per item", flush=True)
    secs = (time.time() - t0) / N
    raw = pl.DataFrame({"article_id": items["article_id"], "raw_tags": raw_tags, "raw_summary": raw_sum, "secs": [secs] * N})
    raw.write_parquet(CACHE)

# Clean up: split on commas, drop empties, keep the first 5 (the model often lists more than asked)
tag_lists = [[t.strip(" .#\"'").lower() for t in s.split(",") if t.strip(" .#\"'")][:5] for s in raw["raw_tags"]]
llm_tags = [", ".join(t) for t in tag_lists]
summary = raw["raw_summary"].to_list()
n_raw = np.array([len([t for t in s.split(",") if t.strip()]) for s in raw["raw_tags"]])
n_words = np.array([len(s.split()) for s in summary])
print(f"\nTags: {np.mean(n_raw >= 3):.0%} gave 3+ tags, {np.mean(n_raw == 5):.0%} gave exactly 5 (median {np.median(n_raw):.0f})")
print(f"Summary: median {np.median(n_words):.0f} words, {np.mean(n_words <= 15):.0%} kept to the 15-word limit")
print(f"Speed: {secs:.1f}s per item on CPU (both tasks)")

# 4. Checks. Grounding: share of tag words that appear in the description / colour / type (low = made-up facts)
words = lambda s: {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", s.lower())}


def grounded(tag_str, r):
    src = words(f"{r['detail_desc']} {r['colour_group_name']} {r['product_type_name']}")
    w = words(tag_str)
    return len(w & src) / len(w) if w else np.nan


g_llm = np.array([grounded(t, r) for t, r in zip(llm_tags, rows)])
g_base = np.array([grounded(t, r) for t, r in zip(base_tags, rows)])
g_sum = np.array([grounded(s, r) for s, r in zip(summary, rows)])
colour_hit = np.mean([r["colour_group_name"].lower().split()[-1] in f"{t} {s}".lower() for t, s, r in zip(llm_tags, summary, rows)])

# Usefulness: can a search engine guess the product type from the tags alone? (MiniLM: tags -> closest type name)
mini = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
type_names = sorted(arts["product_type_name"].unique().to_list())
T = mini.encode(type_names, normalize_embeddings=True, show_progress_bar=False)
truth = items["product_type_name"].to_numpy()


def type_acc(texts):
    E = mini.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return (np.array(type_names)[(E @ T.T).argmax(1)] == truth).mean()


print("\n                                   grounded words   type guessed from text")
print(f"  {'Full description (reference)':32s}        -            {type_acc(items['detail_desc'].to_list()):6.1%}")
print(f"  {'TF-IDF top-5 words (no AI)':32s}  {np.nanmean(g_base):10.1%}          {type_acc(base_tags):6.1%}")
print(f"  {'SmolLM2 tags':32s}  {np.nanmean(g_llm):10.1%}          {type_acc(llm_tags):6.1%}")
print(f"  {'SmolLM2 one-line summary':32s}  {np.nanmean(g_sum):10.1%}          {type_acc(summary):6.1%}")
print(f"  SmolLM2 mentions the right colour: {colour_hit:.1%}")

print("\nLeast grounded tags (most words not in the source):")
for i in np.argsort(g_llm)[:3]:
    print(f"  {g_llm[i]:.0%}  [{rows[i]['product_type_name']}] {llm_tags[i]}  <- {rows[i]['detail_desc'][:80]}")

print("\nExamples:")
for i in np.random.default_rng(SEED).choice(N, 4, replace=False):
    r = rows[i]
    print(f"- [{r['product_type_name']}, {r['colour_group_name']}] {r['detail_desc'][:100]}")
    print(f"    TF-IDF : {base_tags[i]}")
    print(f"    SmolLM2: {llm_tags[i]}")
    print(f"    Summary: {summary[i]}")

items.select(["article_id", "product_type_name", "colour_group_name", "detail_desc"]).with_columns(
    pl.Series("tfidf_tags", base_tags), pl.Series("llm_tags", llm_tags), pl.Series("llm_summary", summary),
    pl.Series("grounded", g_llm),
).write_parquet("data/clean/genai_tags.parquet")
