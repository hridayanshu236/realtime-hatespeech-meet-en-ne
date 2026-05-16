import os
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# ── Config ────────────────────────────────────────────────────────────────────

LABELS = ["clean", "profanity", "hate_speech", "threat", "identity_attack"]

# Per-label thresholds. Lower = more sensitive.
# Threat is set lower because missing a threat is worse than a false positive.
THRESHOLDS = {
    "clean":           0.5,
    "profanity":       0.5,
    "hate_speech":     0.4,
    "threat":          0.3,
    "identity_attack": 0.4,
}

MODEL_PATH = os.path.join(os.path.dirname(__file__), "xlmr-final")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# ── Load model once at import time ───────────────────────────────────────────

print(f"Loading GuardMeet model from {MODEL_PATH} on {DEVICE}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model = model.to(DEVICE)
model.eval()
print("Model ready.")

# ── Inference ─────────────────────────────────────────────────────────────────

def predict(text: str, thresholds: dict = THRESHOLDS) -> dict:
    """
    Classify a single text string for hate speech and profanity.

    Args:
        text: Plain text in English, Nepali, or code-switched.
        thresholds: Dict mapping label name to float threshold (0-1).

    Returns:
        {
            "flagged_labels": ["hate_speech"],        # labels above threshold
            "is_harmful": True,                       # any non-clean label flagged
            "scores": {
                "clean":           {"prob": 0.03, "flagged": False},
                "profanity":       {"prob": 0.12, "flagged": False},
                "hate_speech":     {"prob": 0.91, "flagged": True},
                "threat":          {"prob": 0.08, "flagged": False},
                "identity_attack": {"prob": 0.04, "flagged": False},
            }
        }
    """
    if not text or not text.strip():
        return {
            "flagged_labels": [],
            "is_harmful": False,
            "scores": {lbl: {"prob": 0.0, "flagged": False} for lbl in LABELS}
        }

    enc = tokenizer(
        text,
        max_length=128,
        padding="max_length",
        truncation=True,
        return_tensors="pt"
    )

    with torch.no_grad():
        logits = model(
            input_ids=enc["input_ids"].to(DEVICE),
            attention_mask=enc["attention_mask"].to(DEVICE)
        ).logits

    probs = torch.sigmoid(logits).squeeze().cpu().numpy()

    scores = {
        lbl: {
            "prob": round(float(p), 4),
            "flagged": bool(p >= thresholds.get(lbl, 0.5))
        }
        for lbl, p in zip(LABELS, probs)
    }

    flagged_labels = [
        lbl for lbl in LABELS
        if scores[lbl]["flagged"] and lbl != "clean"
    ]

    return {
        "flagged_labels": flagged_labels,
        "is_harmful": len(flagged_labels) > 0,
        "scores": scores
    }


def predict_batch(texts: list[str], thresholds: dict = THRESHOLDS) -> list[dict]:
    """
    Classify a batch of texts at once. Faster than calling predict() in a loop.

    Args:
        texts: List of plain text strings.
        thresholds: Dict mapping label name to float threshold.

    Returns:
        List of result dicts in the same order as input texts.
    """
    if not texts:
        return []

    enc = tokenizer(
        texts,
        max_length=128,
        padding="max_length",
        truncation=True,
        return_tensors="pt"
    )

    with torch.no_grad():
        logits = model(
            input_ids=enc["input_ids"].to(DEVICE),
            attention_mask=enc["attention_mask"].to(DEVICE)
        ).logits

    all_probs = torch.sigmoid(logits).cpu().numpy()

    results = []
    for probs in all_probs:
        scores = {
            lbl: {
                "prob": round(float(p), 4),
                "flagged": bool(p >= thresholds.get(lbl, 0.5))
            }
            for lbl, p in zip(LABELS, probs)
        }
        flagged_labels = [
            lbl for lbl in LABELS
            if scores[lbl]["flagged"] and lbl != "clean"
        ]
        results.append({
            "flagged_labels": flagged_labels,
            "is_harmful": len(flagged_labels) > 0,
            "scores": scores
        })

    return results


# ── Quick test when run directly ──────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        "You faggot",
        "you fucking muslim terrorist",
        "Great meeting everyone, see you next week!",
        "I will hurt you if you say that again",
        "तिमि हरु यहाँ बाट जाउ, मलाई घृणा लाग्छ",
        "म हान्छु गोली अब आयेर सबै चोरहरुलाई",
        "yo kasto manchhe ho, get out of this meeting"
    ]

    print("\n" + "=" * 60)
    for text in test_cases:
        result = predict(text)
        print(f"\nText: {text[:55]}")
        print(f"  Harmful:  {result['is_harmful']}")
        print(f"  Flagged:  {result['flagged_labels'] or 'none'}")
        for lbl, v in result["scores"].items():
            bar = "|" * int(v["prob"] * 20)
            flag = " <-- FLAGGED" if v["flagged"] and lbl != "clean" else ""
            print(f"  {lbl:20s} {v['prob']:.4f}  {bar}{flag}")
    print("=" * 60)