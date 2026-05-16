"""
src/train_baselines.py

Trains four baseline models for academic comparison against XLM-RoBERTa.
Each model represents a different paradigm of text classification:

1. TF-IDF + Logistic Regression — classical statistical NLP
2. TF-IDF + Linear SVM          — classical margin-based classification
3. fastText                     — shallow neural word embeddings
4. mBERT                        — multilingual BERT (strong neural baseline)

These baselines allow us to quantify the improvement from fine-tuning
a large pretrained multilingual transformer (XLM-RoBERTa).
"""

import os
import time
import json
import logging
import joblib
import numpy as np
import pandas as pd
import fasttext
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    classification_report
)
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer
)
from torch.utils.data import Dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(message)s")
log = logging.getLogger(__name__)

os.makedirs("models/baselines/mbert", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)


# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────

def load_splits():
    train = pd.read_csv("data/merged/train.csv").dropna(subset=["text"])
    test  = pd.read_csv("data/merged/test.csv").dropna(subset=["text"])
    train["text"] = train["text"].astype(str)
    test["text"]  = test["text"].astype(str)
    return train, test


def print_metrics(name, y_true, y_pred):
    """Prints a clean metrics table for a given model."""
    print(f"\n{'='*60}")
    print(f"MODEL: {name}")
    print(f"{'='*60}")
    print(f"  Accuracy:  {accuracy_score(y_true, y_pred):.4f}")
    print(f"  F1 (weighted): {f1_score(y_true, y_pred, average='weighted'):.4f}")
    print(f"  F1 (macro):    {f1_score(y_true, y_pred, average='macro'):.4f}")
    print(f"  Precision: {precision_score(y_true, y_pred, average='weighted'):.4f}")
    print(f"  Recall:    {recall_score(y_true, y_pred, average='weighted'):.4f}")
    print(classification_report(y_true, y_pred, target_names=["not hate", "hate"]))


# ─────────────────────────────────────────────
# MODEL 1: TF-IDF + LOGISTIC REGRESSION
# ─────────────────────────────────────────────

def train_lr(train, test):
    log.info("Training TF-IDF + Logistic Regression...")
    start = time.time()

    vectorizer = TfidfVectorizer(max_features=50000, ngram_range=(1, 2), sublinear_tf=True)
    X_train = vectorizer.fit_transform(train["text"])
    X_test  = vectorizer.transform(test["text"])

    model = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced", solver="lbfgs")
    model.fit(X_train, train["label"])

    y_pred = model.predict(X_test)
    elapsed = time.time() - start

    print_metrics("TF-IDF + Logistic Regression", test["label"], y_pred)
    log.info(f"Training time: {elapsed:.1f}s")

    joblib.dump(model,      "models/baselines/tfidf_lr.joblib")
    joblib.dump(vectorizer, "models/baselines/tfidf_vectorizer.joblib")
    log.info("Saved: models/baselines/tfidf_lr.joblib, tfidf_vectorizer.joblib")

    return vectorizer, y_pred


# ─────────────────────────────────────────────
# MODEL 2: TF-IDF + LINEAR SVM
# ─────────────────────────────────────────────

def train_svm(train, test, vectorizer):
    log.info("Training TF-IDF + Linear SVM...")
    start = time.time()

    X_train = vectorizer.transform(train["text"])
    X_test  = vectorizer.transform(test["text"])

    model = LinearSVC(C=1.0, max_iter=2000, class_weight="balanced")
    model.fit(X_train, train["label"])

    y_pred = model.predict(X_test)
    elapsed = time.time() - start

    print_metrics("TF-IDF + Linear SVM", test["label"], y_pred)
    log.info(f"Training time: {elapsed:.1f}s")

    joblib.dump(model, "models/baselines/tfidf_svm.joblib")
    log.info("Saved: models/baselines/tfidf_svm.joblib")

    return y_pred


# ─────────────────────────────────────────────
# MODEL 3: fastText
# ─────────────────────────────────────────────

def df_to_fasttext_format(df: pd.DataFrame, filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            text = str(row["text"]).replace("\n", " ").replace("\r", " ").strip()
            f.write(f"__label__{int(row['label'])} {text}\n")
    log.info(f"Saved fastText format to {filepath} ({len(df)} examples)")


def train_fasttext(train, test):
    log.info("Training fastText...")

    train_path = "data/processed/train_ft.txt"
    test_path  = "data/processed/test_ft.txt"
    df_to_fasttext_format(train, train_path)
    df_to_fasttext_format(test,  test_path)

    start = time.time()

    model = fasttext.train_supervised(
        input=train_path,
        epoch=25,
        lr=0.5,
        wordNgrams=2,
        dim=100,
        loss="softmax"
    )

    elapsed = time.time() - start

    test_texts = test["text"].tolist()
    y_pred = []
    for text in test_texts:
        text_clean = text.replace("\n", " ").strip()
        pred_label = model.predict(text_clean)[0][0]
        y_pred.append(int(pred_label.replace("__label__", "")))

    print_metrics("fastText", test["label"], y_pred)
    log.info(f"Training time: {elapsed:.1f}s")

    model.save_model("models/baselines/fasttext_model.bin")
    log.info("Saved: models/baselines/fasttext_model.bin")

    return y_pred


# ─────────────────────────────────────────────
# MODEL 4: mBERT
# ─────────────────────────────────────────────

class HateSpeechDataset(Dataset):
    def __init__(self, df: pd.DataFrame, tokenizer, max_length: int = 128):
        self.labels = df["label"].tolist()
        self.encodings = tokenizer(
            df["text"].tolist(),
            padding="max_length",
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        )

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            "input_ids":      self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "labels":         torch.tensor(self.labels[idx], dtype=torch.long)
        }


def compute_metrics_hf(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy":  accuracy_score(labels, preds),
        "f1":        f1_score(labels, preds, average="weighted"),
        "precision": precision_score(labels, preds, average="weighted"),
        "recall":    recall_score(labels, preds, average="weighted"),
    }


def train_mbert(train, test):
    log.info("Training mBERT...")

    MODEL_NAME = "bert-base-multilingual-cased"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model     = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    train_dataset = HateSpeechDataset(train, tokenizer)
    test_dataset  = HateSpeechDataset(test,  tokenizer)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_mem = torch.cuda.get_device_properties(0).total_memory // (1024**3) if device == "cuda" else 0
    batch_size = 32 if gpu_mem >= 30 else 16

    args = TrainingArguments(
        output_dir="models/baselines/mbert",
        num_train_epochs=3,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        learning_rate=2e-5,
        weight_decay=0.01,
        logging_steps=100,
        fp16=(device == "cuda"),
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        compute_metrics=compute_metrics_hf,
    )

    start = time.time()
    trainer.train()
    elapsed = time.time() - start

    preds_output = trainer.predict(test_dataset)
    y_pred = np.argmax(preds_output.predictions, axis=-1)

    print_metrics("mBERT", test["label"], y_pred)
    log.info(f"Training time: {elapsed/60:.1f} minutes")

    trainer.save_model("models/baselines/mbert")
    tokenizer.save_pretrained("models/baselines/mbert")
    log.info("Saved: models/baselines/mbert/")

    return y_pred


if __name__ == "__main__":
    if not os.path.exists("data/merged/train.csv"):
        log.error("Train data not found. Run src/preprocess.py first.")
    else:
        train, test = load_splits()
        log.info(f"Train: {len(train)} | Test: {len(test)}")

        vectorizer, lr_preds   = train_lr(train, test)
        svm_preds              = train_svm(train, test, vectorizer)
        ft_preds               = train_fasttext(train, test)
        # mbert_preds            = train_mbert(train, test)

        log.info("\nAll baseline models trained and saved.")
