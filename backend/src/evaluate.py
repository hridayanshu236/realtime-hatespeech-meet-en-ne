"""
src/evaluate.py

Evaluates all 5 trained models on the held-out test set.
Produces metrics, comparison table, confusion matrices, and error analysis.
"""

import os
import json
import joblib
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import fasttext
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    classification_report, confusion_matrix
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(message)s")
log = logging.getLogger(__name__)

os.makedirs("results", exist_ok=True)


# ─────────────────────────────────────────────
# CORE EVALUATION FUNCTIONS
# ─────────────────────────────────────────────

def evaluate_model(model_name: str, y_true, y_pred) -> dict:
    metrics = {
        "accuracy":    round(accuracy_score(y_true, y_pred), 4),
        "f1_weighted": round(f1_score(y_true, y_pred, average="weighted"), 4),
        "f1_macro":    round(f1_score(y_true, y_pred, average="macro"), 4),
        "precision":   round(precision_score(y_true, y_pred, average="weighted"), 4),
        "recall":      round(recall_score(y_true, y_pred, average="weighted"), 4),
    }

    print(f"\n{'='*60}")
    print(f"MODEL: {model_name}")
    print(f"{'='*60}")
    for k, v in metrics.items():
        print(f"  {k:<20} {v:.4f}")
    print(classification_report(y_true, y_pred, target_names=["not hate", "hate"]))

    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=["not hate", "hate"],
        yticklabels=["not hate", "hate"],
        ax=ax
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(f"Confusion Matrix — {model_name}")
    plt.tight_layout()
    safe_name = model_name.lower().replace(" ", "_").replace("+", "")
    plt.savefig(f"results/{safe_name}_confusion_matrix.png", dpi=150)
    plt.close()
    log.info(f"Saved confusion matrix: results/{safe_name}_confusion_matrix.png")

    return metrics


def evaluate_by_language(model_name: str, y_true, y_pred, languages) -> dict:
    y_true  = np.array(y_true)
    y_pred  = np.array(y_pred)
    langs   = np.array(languages)

    results = {}
    for lang in ["en", "ne"]:
        mask = langs == lang
        if mask.sum() == 0:
            results[f"f1_{lang}"] = None
            continue
        f1 = f1_score(y_true[mask], y_pred[mask], average="weighted")
        results[f"f1_{lang}"] = round(f1, 4)
        print(f"  [{model_name}] F1 on {lang.upper()}: {f1:.4f} ({mask.sum()} samples)")

    return results


# ─────────────────────────────────────────────
# MODEL PREDICTORS
# ─────────────────────────────────────────────

def predict_sklearn(model_path: str, vectorizer_path: str, texts):
    if not os.path.exists(model_path) or not os.path.exists(vectorizer_path):
        return [0] * len(texts)
    model      = joblib.load(model_path)
    vectorizer = joblib.load(vectorizer_path)
    X          = vectorizer.transform(texts)
    return model.predict(X).tolist()


def predict_fasttext(model_path: str, texts):
    if not os.path.exists(model_path):
        return [0] * len(texts)
    model = fasttext.load_model(model_path)
    preds = []
    for text in texts:
        text_clean = str(text).replace("\n", " ").strip()
        label = model.predict(text_clean)[0][0]
        preds.append(int(label.replace("__label__", "")))
    return preds


def predict_transformer(model_dir: str, texts, batch_size: int = 32):
    if not os.path.exists(model_dir) or not os.path.exists(os.path.join(model_dir, "config.json")):
        return [0] * len(texts)
    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model     = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.to(device)
    model.eval()

    all_preds = []
    for i in range(0, len(texts), batch_size):
        batch_texts = [str(t) for t in texts[i: i + batch_size]]
        enc = tokenizer(
            batch_texts,
            padding="max_length",
            truncation=True,
            max_length=128,
            return_tensors="pt"
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            logits = model(**enc).logits
        preds = torch.argmax(logits, dim=-1).cpu().tolist()
        all_preds.extend(preds)

    return all_preds


# ─────────────────────────────────────────────
# ERROR ANALYSIS
# ─────────────────────────────────────────────

def error_analysis(test_df: pd.DataFrame, y_pred):
    test_df = test_df.copy()
    test_df["predicted"] = y_pred
    test_df["correct"]   = (test_df["label"] == test_df["predicted"])

    fp = test_df[(test_df["predicted"] == 1) & (test_df["label"] == 0)]
    fn = test_df[(test_df["predicted"] == 0) & (test_df["label"] == 1)]

    fp.head(20).to_csv("results/false_positives.csv", index=False)
    fn.head(20).to_csv("results/false_negatives.csv", index=False)

    log.info(f"Error analysis: {len(fp)} false positives, {len(fn)} false negatives")


# ─────────────────────────────────────────────
# MAIN EVALUATION PIPELINE
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists("data/merged/test.csv"):
        log.error("Test data not found. Run src/preprocess.py first.")
    else:
        test_df  = pd.read_csv("data/merged/test.csv").dropna(subset=["text"])
        test_df["text"] = test_df["text"].astype(str)
        texts    = test_df["text"].tolist()
        y_true   = test_df["label"].tolist()
        languages = test_df["language"].tolist()

        all_metrics = {}
        models_config = [
            ("LR + TF-IDF",       lambda t: predict_sklearn("models/baselines/tfidf_lr.joblib",
                                                             "models/baselines/tfidf_vectorizer.joblib", t)),
            ("SVM + TF-IDF",      lambda t: predict_sklearn("models/baselines/tfidf_svm.joblib",
                                                              "models/baselines/tfidf_vectorizer.joblib", t)),
            ("fastText",          lambda t: predict_fasttext("models/baselines/fasttext_model.bin", t)),
            ("mBERT",             lambda t: predict_transformer("models/baselines/mbert", t)),
            ("XLM-RoBERTa (ours)",lambda t: predict_transformer("models/xlm_roberta/final", t)),
        ]

        for model_name, predictor in models_config:
            log.info(f"Evaluating {model_name}...")
            y_pred = predictor(texts)
            m      = evaluate_model(model_name, y_true, y_pred)
            lang_m = evaluate_by_language(model_name, y_true, y_pred, languages)
            m.update(lang_m)
            all_metrics[model_name] = m

            if model_name == "XLM-RoBERTa (ours)":
                error_analysis(test_df, y_pred)

        with open("results/metrics.json", "w") as f:
            json.dump(all_metrics, f, indent=2)

        rows = []
        for model_name, m in all_metrics.items():
            rows.append({
                "Model":         model_name,
                "Accuracy":      m.get("accuracy"),
                "F1 (weighted)": m.get("f1_weighted"),
                "F1 (macro)":    m.get("f1_macro"),
                "F1-EN":         m.get("f1_en"),
                "F1-NE":         m.get("f1_ne"),
            })
        table = pd.DataFrame(rows)
        print("\nCOMPARISON TABLE\n", table.to_string(index=False))
        table.to_csv("results/comparison_table.csv", index=False)
