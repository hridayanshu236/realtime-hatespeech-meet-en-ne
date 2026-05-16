"""
src/preprocess.py

Data loading, cleaning, label unification, merging, and splitting
for the multilingual hate speech detection project.

Produces:
    data/merged/train.csv
    data/merged/val.csv
    data/merged/test.csv
    data/merged/class_weights.json
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(message)s")
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# INDIVIDUAL DATASET LOADERS
# Each function returns a DataFrame with exactly
# two columns: text (str) and label (int: 0 or 1)
# ─────────────────────────────────────────────

def load_jigsaw(path: str = "data/raw/jigsaw/train.csv") -> pd.DataFrame:
    """
    Jigsaw Toxic Comment Classification (Kaggle, ~159k comments).
    Multi-label: toxic, severe_toxic, obscene, threat, insult, identity_hate.
    Unification: label=1 if ANY toxic column is 1, else label=0.
    This is the most conservative unification strategy — any toxic signal
    means the comment is considered harmful.
    """
    log.info("Loading Jigsaw dataset...")
    if not os.path.exists(path):
        log.warning(f"Jigsaw dataset not found at {path}. Skipping.")
        return pd.DataFrame(columns=["text", "label"])
    df = pd.read_csv(path)
    toxic_cols = ["toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"]
    df["label"] = (df[toxic_cols].sum(axis=1) > 0).astype(int)
    df = df.rename(columns={"comment_text": "text"})[["text", "label"]]
    return _clean(df, "Jigsaw")


def load_davidson(path: str = "data/raw/davidson/labeled_data.csv") -> pd.DataFrame:
    """
    Davidson Hate Speech and Offensive Language Dataset (Kaggle, ~25k tweets).
    3-class: 0=hate speech, 1=offensive language, 2=neither.
    Unification: label=0 only if class==2 (neither), else label=1.
    We treat both hate speech AND offensive language as harmful — the distinction
    between them is not meaningful for a real-time moderation system.
    """
    log.info("Loading Davidson dataset...")
    if not os.path.exists(path):
        log.warning(f"Davidson dataset not found at {path}. Skipping.")
        return pd.DataFrame(columns=["text", "label"])
    df = pd.read_csv(path)
    df["label"] = (df["class"] != 2).astype(int)
    df = df.rename(columns={"tweet": "text"})[["text", "label"]]
    return _clean(df, "Davidson")


def load_tweets_hate_speech() -> pd.DataFrame:
    """
    Tweets Hate Speech Detection (HuggingFace, ~31k tweets).
    Binary: 0=no hate speech, 1=hate speech.
    Labels are already in the correct binary format.
    Used instead of HatEval which requires manual ToS agreement on HuggingFace.
    """
    log.info("Loading Tweets Hate Speech Detection dataset...")
    try:
        ds = load_dataset("tweets_hate_speech_detection", split="train")
        df = pd.DataFrame({"text": ds["tweet"], "label": ds["label"]})
        return _clean(df, "TweetsHate")
    except Exception as e:
        log.error(f"Failed to load Tweets Hate Speech dataset: {e}")
        return pd.DataFrame(columns=["text", "label"])


def load_hatexplain() -> pd.DataFrame:
    """
    HateXplain (HuggingFace, ~20k posts).
    Labels come from multiple annotators per post. Each annotator assigns:
        0 = hatespeech, 1 = offensive, 2 = normal
    We take the MAJORITY VOTE across annotators.
    Unification: majority 0 or 1 → label=1 (harmful); majority 2 → label=0 (normal).

    Why majority vote instead of any-annotator?
    Majority vote is more robust to individual annotator bias and is the
    standard practice in NLP disagreement resolution.
    """
    log.info("Loading HateXplain dataset...")
    try:
        ds = load_dataset("hatexplain", split="train")

        rows = []
        for item in ds:
            # post_tokens is a list of word tokens; join them into a sentence
            text = " ".join(item["post_tokens"])
            # annotators["label"] is a list of integers (one per annotator)
            annotator_labels = item["annotators"]["label"]
            # Majority vote: count occurrences and pick the most common
            majority = max(set(annotator_labels), key=annotator_labels.count)
            # Map: 0=hatespeech→1, 1=offensive→1, 2=normal→0
            label = 0 if majority == 2 else 1
            rows.append({"text": text, "label": label})

        df = pd.DataFrame(rows)
        return _clean(df, "HateXplain")
    except Exception as e:
        log.error(f"Failed to load HateXplain dataset: {e}")
        return pd.DataFrame(columns=["text", "label"])


def load_nepali(path: str = "data/raw/nepali_dataset.csv") -> pd.DataFrame:
    """
    Nepali hate speech dataset (provided by teammate Sumira).
    Expected columns: text (str), label (int: 0 or 1).
    Labels must already be in binary format — validated below.
    """
    log.info("Loading Nepali dataset...")
    if not os.path.exists(path):
        log.warning(f"Nepali dataset not found at {path}. Skipping.")
        return pd.DataFrame(columns=["text", "label"])

    df = pd.read_csv(path)[["text", "label"]]

    # Validate labels are strictly binary
    invalid = df[~df["label"].isin([0, 1])]
    if len(invalid) > 0:
        log.warning(f"Found {len(invalid)} rows with invalid labels in Nepali dataset. Dropping.")
        df = df[df["label"].isin([0, 1])]

    return _clean(df, "Nepali")


# ─────────────────────────────────────────────
# TEXT CLEANING
# ─────────────────────────────────────────────

def _clean(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    Applies standard cleaning to any dataset:
    1. Drop rows where text is NaN
    2. Convert text to string (handles any accidental numeric types)
    3. Strip leading/trailing whitespace
    4. Drop rows where text is empty or fewer than 3 characters
       (3-char minimum eliminates meaningless fragments like "ok" or "no"
        that provide no signal for hate speech detection)
    5. Drop exact duplicate texts (same string, keep first occurrence)
    6. Ensure label is integer dtype

    Returns a DataFrame with columns: text (str), label (int)
    """
    before = len(df)
    df = df.dropna(subset=["text"])
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() >= 3]
    df = df.drop_duplicates(subset=["text"])
    df["label"] = df["label"].astype(int)
    after = len(df)
    log.info(f"{name}: {before} → {after} rows after cleaning "
             f"(removed {before - after}). "
             f"Label dist: {df['label'].value_counts().to_dict()}")
    return df.reset_index(drop=True)


# ─────────────────────────────────────────────
# MERGE AND SPLIT
# ─────────────────────────────────────────────

def merge_and_split(random_state: int = 42):
    """
    Loads all datasets, merges them, adds language tags,
    splits 80/10/10, saves to data/merged/, computes class weights.

    Why 80/10/10?
    Standard academic split. 10% validation lets us monitor overfitting
    during training; 10% test gives a held-out set for final unbiased evaluation.

    Why stratify=df['label']?
    Stratification ensures the same class ratio (hate vs not-hate) appears
    in train, val, and test. Without it, random chance could create an
    unrepresentative test set.
    """
    os.makedirs("data/merged", exist_ok=True)

    # Load all datasets
    dfs = []

    # English datasets — each tagged with language="en"
    for loader, tag in [
        (load_jigsaw,             "en"),
        (load_davidson,           "en"),
        (load_tweets_hate_speech, "en"),
        (load_hatexplain,         "en"),
    ]:
        df = loader()
        if len(df) > 0:
            df["language"] = tag
            dfs.append(df)

    # Nepali dataset — tagged language="ne"
    df_ne = load_nepali()
    if len(df_ne) > 0:
        df_ne["language"] = "ne"
        dfs.append(df_ne)

    if not dfs:
        log.error("No datasets loaded. Exiting.")
        return None, None, None

    # Concatenate and shuffle
    merged = pd.concat(dfs, ignore_index=True)
    merged = merged.sample(frac=1, random_state=random_state).reset_index(drop=True)

    log.info(f"\n{'='*50}")
    log.info(f"TOTAL MERGED: {len(merged)} samples")
    log.info(f"Label distribution:\n{merged['label'].value_counts()}")
    log.info(f"Language distribution:\n{merged['language'].value_counts()}")

    # 80/10/10 split, stratified on label
    train, temp = train_test_split(
        merged, test_size=0.2, random_state=random_state, stratify=merged["label"]
    )
    val, test = train_test_split(
        temp, test_size=0.5, random_state=random_state, stratify=temp["label"]
    )

    # Save splits
    train.to_csv("data/merged/train.csv", index=False)
    val.to_csv("data/merged/val.csv",   index=False)
    test.to_csv("data/merged/test.csv",  index=False)

    for split_name, split_df in [("TRAIN", train), ("VAL", val), ("TEST", test)]:
        log.info(f"\n{split_name}: {len(split_df)} samples")
        log.info(f"  Labels: {split_df['label'].value_counts().to_dict()}")
        log.info(f"  Languages: {split_df['language'].value_counts().to_dict()}")

    # ─── Class Imbalance Analysis ───
    labels = train["label"].values
    n_pos = (labels == 1).sum()
    n_neg = (labels == 0).sum()
    ratio = n_neg / n_pos if n_pos > 0 else float("inf")

    log.info(f"\nCLASS IMBALANCE (train set):")
    log.info(f"  Hate (1):     {n_pos} ({100*n_pos/len(labels):.1f}%)")
    log.info(f"  Not hate (0): {n_neg} ({100*n_neg/len(labels):.1f}%)")
    log.info(f"  Imbalance ratio (neg/pos): {ratio:.2f}x")

    # compute_class_weight('balanced') calculates:
    #   weight[c] = n_samples / (n_classes * n_samples_in_class_c)
    # This means the minority class (hate speech) gets a higher weight,
    # forcing the model to pay more attention to it during training.
    class_weights = compute_class_weight(
        class_weight="balanced",
        classes=np.array([0, 1]),
        y=labels
    )
    weights_dict = {"0": float(class_weights[0]), "1": float(class_weights[1])}
    log.info(f"  Computed class weights: {weights_dict}")

    with open("data/merged/class_weights.json", "w") as f:
        json.dump(weights_dict, f, indent=2)

    log.info("Saved: data/merged/train.csv, val.csv, test.csv, class_weights.json")
    return train, val, test


if __name__ == "__main__":
    merge_and_split()
