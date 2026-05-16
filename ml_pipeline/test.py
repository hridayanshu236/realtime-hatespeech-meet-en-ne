import traceback
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_PATH = "./xlmr-final"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
print("Tokenizer loaded.")

print("Loading model...")
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
print("Model loaded.")