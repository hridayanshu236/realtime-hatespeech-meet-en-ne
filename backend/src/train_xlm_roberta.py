"""
src/train_xlm_roberta.py

Fine-tunes XLM-RoBERTa for multilingual hate speech classification.
"""

import os
import json
import time
import logging
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer
)
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(message)s")
log = logging.getLogger(__name__)

os.makedirs("models/xlm_roberta/checkpoints", exist_ok=True)
os.makedirs("models/xlm_roberta/final", exist_ok=True)

MODEL_NAME = "xlm-roberta-base"


# ─────────────────────────────────────────────
# DATASET CLASS
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


# ─────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy":    accuracy_score(labels, preds),
        "f1_weighted": f1_score(labels, preds, average="weighted"),
        "f1_macro":    f1_score(labels, preds, average="macro"),
        "precision":   precision_score(labels, preds, average="weighted"),
        "recall":      recall_score(labels, preds, average="weighted"),
    }


# ─────────────────────────────────────────────
# WEIGHTED LOSS TRAINER
# ─────────────────────────────────────────────

class WeightedTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits

        # Load class weights (computed in preprocess.py)
        with open("data/merged/class_weights.json") as f:
            cw = json.load(f)
        weight_tensor = torch.tensor(
            [cw["0"], cw["1"]], dtype=torch.float32
        ).to(logits.device)

        loss_fn = nn.CrossEntropyLoss(weight=weight_tensor)
        loss = loss_fn(logits, labels)

        return (loss, outputs) if return_outputs else loss


# ─────────────────────────────────────────────
# TRAINING ARGUMENTS
# ─────────────────────────────────────────────

def get_training_args() -> TrainingArguments:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_mem = torch.cuda.get_device_properties(0).total_memory // (1024**3) if device == "cuda" else 0
    batch_size = 32 if gpu_mem >= 30 else 16

    return TrainingArguments(
        output_dir="models/xlm_roberta/checkpoints",
        num_train_epochs=5,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        learning_rate=2e-5,
        weight_decay=0.01,
        warmup_ratio=0.1,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_weighted",
        greater_is_better=True,
        logging_steps=100,
        fp16=(device == "cuda"),
        dataloader_num_workers=2,
        report_to="none",
    )


# ─────────────────────────────────────────────
# MAIN TRAINING LOOP
# ─────────────────────────────────────────────

def train():
    log.info(f"Loading model and tokenizer: {MODEL_NAME}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model     = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=2
    )

    log.info("Loading data...")
    if not os.path.exists("data/merged/train.csv"):
        log.error("Train data not found. Run src/preprocess.py first.")
        return

    train_df = pd.read_csv("data/merged/train.csv").dropna(subset=["text"])
    val_df   = pd.read_csv("data/merged/val.csv").dropna(subset=["text"])
    train_df["text"] = train_df["text"].astype(str)
    val_df["text"]   = val_df["text"].astype(str)

    log.info(f"Train: {len(train_df)} | Val: {len(val_df)}")

    log.info("Tokenizing datasets...")
    train_dataset = HateSpeechDataset(train_df, tokenizer)
    val_dataset   = HateSpeechDataset(val_df,   tokenizer)

    training_args = get_training_args()

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    log.info("Starting training...")
    start = time.time()
    trainer.train()
    elapsed = time.time() - start

    log.info(f"\nTraining complete in {elapsed/60:.1f} minutes")
    log.info(f"Best val F1 (weighted): {trainer.state.best_metric:.4f}")
    log.info(f"Best checkpoint: {trainer.state.best_model_checkpoint}")

    trainer.save_model("models/xlm_roberta/final")
    tokenizer.save_pretrained("models/xlm_roberta/final")
    log.info("Saved final model to: models/xlm_roberta/final/")


if __name__ == "__main__":
    train()
