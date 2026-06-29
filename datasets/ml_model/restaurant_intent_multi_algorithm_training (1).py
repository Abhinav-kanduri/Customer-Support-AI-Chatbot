# -*- coding: utf-8 -*-
"""restaurant_intent_multi_algorithm_training.ipynb


# Restaurant Intent Classification — Multi-Algorithm Training Notebook

## Goal

Build an end-to-end intent classification model for a restaurant customer support AI chatbot.

**Input:** customer `statement`  
**Final output:** predicted `intent_code`

Example:

```json
{
  "statement": "I was charged twice for my order.",
  "predicted_intent": "DOUBLE_CHARGED",
  "confidence": 0.94
}
```

This notebook trains multiple algorithms, compares accuracy/F1 score, saves all candidate models, selects the best model, and exports the best model as a `.pkl` file.

## Intent Classes

The final model should predict one of these restaurant support intents:

```text
ORDER_STATUS
ORDER_DELAYED
ORDER_NOT_RECEIVED
MISSING_ITEM
WRONG_ITEM
FOOD_QUALITY_ISSUE
FOOD_SAFETY_ISSUE
PAYMENT_FAILED
DOUBLE_CHARGED
REFUND_REQUEST
RESERVATION_CREATE
RESERVATION_MODIFY
RESERVATION_CANCEL
MENU_INQUIRY
ALLERGY_INQUIRY
PROMO_CODE_ISSUE
LOYALTY_POINTS_ISSUE
STAFF_COMPLAINT
CLEANLINESS_COMPLAINT
LOST_AND_FOUND
CATERING_INQUIRY
HUMAN_AGENT_REQUEST
GENERAL_INQUIRY
OUT_OF_SCOPE
```

## Algorithms Implemented

This notebook trains and compares:

| Algorithm | Feature Method | Output |
|---|---|---|
| Dummy Classifier | Baseline | `intent_code` |
| Multinomial Naive Bayes | Word TF-IDF | `intent_code` |
| Complement Naive Bayes | Word TF-IDF | `intent_code` |
| Logistic Regression | Word TF-IDF | `intent_code` |
| Linear SVM | Word TF-IDF | `intent_code` |
| SGD Classifier | Word TF-IDF | `intent_code` |
| Logistic Regression | Character TF-IDF | `intent_code` |
| Hybrid Feature Model | Word + Character TF-IDF | `intent_code` |

The notebook selects the best model using:

1. Highest macro F1 score
2. Highest accuracy
3. Lowest training time as a tie-breaker
"""

# Optional installation commands if running in a fresh local environment.
# Uncomment if needed.

# !pip install pandas numpy scikit-learn joblib matplotlib seaborn

import os
import re
import json
import time
import joblib
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.dummy import DummyClassifier
from sklearn.naive_bayes import MultinomialNB, ComplementNB
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix
)

warnings.filterwarnings("ignore")
pd.set_option("display.max_colwidth", 120)

"""## 1. Configuration

Set the dataset path. The notebook supports:

1. Two-column dataset with `statement` and `intent_code`
2. Rich dataset that includes additional metadata and optional `split` column
"""

# Change this path if your dataset file is stored somewhere else.
DATA_PATH = "datasets/restaurant_intent_dataset_36000_two_columns (1).csv"

# Fallback path for the richer dataset.
FALLBACK_DATA_PATH = 'datasets/restaurant_intent_dataset_31200 (1).csv'

TEXT_COLUMN = "statement"
TARGET_COLUMN = "intent_code"

ARTIFACT_DIR = Path("datasets/restaurant_intent_model_artifacts")
CANDIDATE_MODEL_DIR = ARTIFACT_DIR / "candidate_models"

ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATE_MODEL_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
TEST_SIZE = 0.20

print("Artifact directory:", ARTIFACT_DIR)

"""## 2. Load Dataset"""

if not os.path.exists(DATA_PATH):
    print(f"Primary DATA_PATH not found: {DATA_PATH}")
    print(f"Using fallback path: {FALLBACK_DATA_PATH}")
    DATA_PATH = FALLBACK_DATA_PATH

df = pd.read_csv(DATA_PATH)

print("Dataset path:", DATA_PATH)
print("Shape:", df.shape)
print("Columns:", list(df.columns))

df.head()

"""## 3. Validate Required Columns"""

required_columns = [TEXT_COLUMN, TARGET_COLUMN]
missing = [col for col in required_columns if col not in df.columns]

if missing:
    raise ValueError(f"Missing required columns: {missing}. Dataset must contain {required_columns}")

df = df.dropna(subset=[TEXT_COLUMN, TARGET_COLUMN]).copy()
df[TEXT_COLUMN] = df[TEXT_COLUMN].astype(str)
df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(str)

print("Rows after dropping nulls:", len(df))
print("Number of intent classes:", df[TARGET_COLUMN].nunique())
print("Intent classes:")
print(sorted(df[TARGET_COLUMN].unique()))

"""## 4. Basic EDA"""

intent_counts = df[TARGET_COLUMN].value_counts().sort_index()
intent_counts_df = intent_counts.reset_index()
intent_counts_df.columns = ["intent_code", "count"]
intent_counts_df

import matplotlib.pyplot as plt

plt.figure(figsize=(12, 6))
df[TARGET_COLUMN].value_counts().plot(kind="bar")
plt.title("Intent Class Distribution")
plt.xlabel("Intent Code")
plt.ylabel("Count")
plt.xticks(rotation=75)
plt.tight_layout()
plt.show()

"""## 5. Text Cleaning

For TF-IDF models, light normalization is usually enough.  
We avoid aggressive cleaning because words like `not`, `missing`, `wrong`, `late`, and `failed` are important for intent classification.
"""

def clean_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text

df["clean_statement"] = df[TEXT_COLUMN].apply(clean_text)

df[[TEXT_COLUMN, "clean_statement", TARGET_COLUMN]].head()

"""## 6. Train/Test Split

If the dataset has a `split` column with train/test labels, the notebook uses it.  
Otherwise, it creates a stratified train/test split.
"""

if "split" in df.columns and set(df["split"].dropna().str.lower().unique()).intersection({"train", "test", "validation", "val"}):
    split_values = df["split"].astype(str).str.lower()
    train_df = df[split_values == "train"].copy()
    test_df = df[split_values.isin(["test", "validation", "val"])].copy()

    if len(train_df) == 0 or len(test_df) == 0:
        print("Split column exists but is not usable. Falling back to stratified train_test_split.")
        train_df, test_df = train_test_split(
            df,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=df[TARGET_COLUMN]
        )
else:
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df[TARGET_COLUMN]
    )

X_train = train_df["clean_statement"]
y_train = train_df[TARGET_COLUMN]

X_test = test_df["clean_statement"]
y_test = test_df[TARGET_COLUMN]

print("Train shape:", train_df.shape)
print("Test shape:", test_df.shape)
print("Train classes:", y_train.nunique())
print("Test classes:", y_test.nunique())

"""## 7. Define Algorithms

Every model is a complete scikit-learn pipeline:

```text
text → TF-IDF vectorizer → classifier → intent_code
```
"""

word_tfidf = TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 2),
    min_df=2,
    max_df=0.95,
    sublinear_tf=True
)

char_tfidf = TfidfVectorizer(
    analyzer="char_wb",
    ngram_range=(3, 5),
    min_df=2,
    max_df=0.95,
    sublinear_tf=True
)

hybrid_features = FeatureUnion([
    ("word_tfidf", TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True
    )),
    ("char_tfidf", TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True
    ))
])

models = {
    "dummy_most_frequent": Pipeline([
        ("tfidf", TfidfVectorizer()),
        ("clf", DummyClassifier(strategy="most_frequent"))
    ]),

    "tfidf_multinomial_nb": Pipeline([
        ("tfidf", word_tfidf),
        ("clf", MultinomialNB(alpha=0.5))
    ]),

    "tfidf_complement_nb": Pipeline([
        ("tfidf", word_tfidf),
        ("clf", ComplementNB(alpha=0.5))
    ]),

    "tfidf_logistic_regression": Pipeline([
        ("tfidf", word_tfidf),
        ("clf", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            solver="lbfgs",
            n_jobs=-1
        ))
    ]),

    "tfidf_linear_svc": Pipeline([
        ("tfidf", word_tfidf),
        ("clf", LinearSVC(
            C=1.0,
            class_weight="balanced",
            random_state=RANDOM_STATE
        ))
    ]),

    "tfidf_sgd_log_loss": Pipeline([
        ("tfidf", word_tfidf),
        ("clf", SGDClassifier(
            loss="log_loss",
            alpha=1e-5,
            max_iter=2000,
            tol=1e-3,
            class_weight="balanced",
            random_state=RANDOM_STATE
        ))
    ]),

    "char_tfidf_logistic_regression": Pipeline([
        ("tfidf", char_tfidf),
        ("clf", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            solver="lbfgs",
            n_jobs=-1
        ))
    ]),

    "hybrid_word_char_logistic_regression": Pipeline([
        ("features", hybrid_features),
        ("clf", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            solver="lbfgs",
            n_jobs=-1
        ))
    ])
}

list(models.keys())

"""## 8. Train and Evaluate All Models

This cell:

1. Trains each model
2. Predicts test labels
3. Calculates accuracy and macro F1
4. Saves each candidate model as `.pkl`
5. Selects the best model
"""

results = []
trained_models = {}

best_model = None
best_model_name = None
best_prediction = None

for model_name, model in models.items():
    print("=" * 90)
    print(f"Training model: {model_name}")

    start_time = time.time()
    model.fit(X_train, y_train)
    train_seconds = time.time() - start_time

    y_pred = model.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    weighted_f1 = f1_score(y_test, y_pred, average="weighted")

    model_file = CANDIDATE_MODEL_DIR / f"{model_name}.pkl"
    joblib.dump(model, model_file)

    row = {
        "model_name": model_name,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "train_seconds": train_seconds,
        "model_file": str(model_file)
    }
    results.append(row)
    trained_models[model_name] = model

    print(f"Accuracy:    {accuracy:.6f}")
    print(f"Macro F1:    {macro_f1:.6f}")
    print(f"Weighted F1: {weighted_f1:.6f}")
    print(f"Train sec:   {train_seconds:.2f}")
    print(f"Saved to:    {model_file}")

results_df = pd.DataFrame(results)

# Best model selection:
# 1. Highest macro F1
# 2. Highest accuracy
# 3. Lowest training time
results_df = results_df.sort_values(
    by=["macro_f1", "accuracy", "train_seconds"],
    ascending=[False, False, True]
).reset_index(drop=True)

best_model_name = results_df.loc[0, "model_name"]
best_model = trained_models[best_model_name]
best_prediction = best_model.predict(X_test)

results_path = ARTIFACT_DIR / "model_comparison.csv"
results_df.to_csv(results_path, index=False)

print("\\nBest model:", best_model_name)
print("Saved model comparison to:", results_path)

results_df

"""## 9. Detailed Classification Report for Best Model"""

print("Best model:", best_model_name)
print(classification_report(y_test, best_prediction))

"""## 10. Confusion Matrix

For many classes, the matrix can be large. This table helps identify which intents get confused.
"""

labels = sorted(y_test.unique())
cm = confusion_matrix(y_test, best_prediction, labels=labels)

cm_df = pd.DataFrame(cm, index=labels, columns=labels)
cm_df

plt.figure(figsize=(14, 12))
plt.imshow(cm, interpolation="nearest")
plt.title(f"Confusion Matrix — {best_model_name}")
plt.colorbar()
tick_marks = np.arange(len(labels))
plt.xticks(tick_marks, labels, rotation=90)
plt.yticks(tick_marks, labels)
plt.xlabel("Predicted Intent")
plt.ylabel("Actual Intent")
plt.tight_layout()
plt.show()

"""## 11. Save Best Model as `.pkl`

This is the production artifact you can load inside FastAPI, LangGraph, or any backend service.

The saved model includes both:

```text
TF-IDF vectorizer + classifier
```

So inference only needs raw customer text.
"""

best_model_path = ARTIFACT_DIR / "best_restaurant_intent_model.pkl"
joblib.dump(best_model, best_model_path)

metadata = {
    "best_model_name": best_model_name,
    "accuracy": float(accuracy_score(y_test, best_prediction)),
    "macro_f1": float(f1_score(y_test, best_prediction, average="macro")),
    "weighted_f1": float(f1_score(y_test, best_prediction, average="weighted")),
    "dataset_path": DATA_PATH,
    "text_column": TEXT_COLUMN,
    "target_column": TARGET_COLUMN,
    "n_rows": int(len(df)),
    "n_train_rows": int(len(train_df)),
    "n_test_rows": int(len(test_df)),
    "n_classes": int(df[TARGET_COLUMN].nunique()),
    "classes": sorted(df[TARGET_COLUMN].unique().tolist()),
    "artifact_path": str(best_model_path)
}

metadata_path = ARTIFACT_DIR / "model_metadata.json"
with open(metadata_path, "w") as f:
    json.dump(metadata, f, indent=2)

print("Best model saved to:", best_model_path)
print("Metadata saved to:", metadata_path)
metadata

"""## 12. Inference Helper

The final model output is the predicted `intent_code`.

The function below returns:

```json
{
  "statement": "...",
  "predicted_intent": "...",
  "confidence": 0.0
}
```

For models with `predict_proba`, confidence is the max probability.  
For models without probability, confidence is estimated from decision scores.
"""

def softmax(x):
    x = np.array(x, dtype=float)
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()

def predict_intent(statement: str, model=None):
    if model is None:
        model = joblib.load(best_model_path)

    cleaned = clean_text(statement)
    predicted_intent = model.predict([cleaned])[0]

    confidence = None

    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba([cleaned])[0]
            confidence = float(np.max(proba))
        except Exception:
            confidence = None

    if confidence is None and hasattr(model, "decision_function"):
        try:
            scores = model.decision_function([cleaned])[0]
            if np.ndim(scores) == 0:
                confidence = float(1 / (1 + np.exp(-scores)))
            else:
                confidence = float(np.max(softmax(scores)))
        except Exception:
            confidence = None

    return {
        "statement": statement,
        "predicted_intent": predicted_intent,
        "confidence": confidence
    }

"""## 13. Test Predictions"""

sample_queries = [
    "Where is my order?",
    "My pizza is 45 minutes late.",
    "I found hair in my food and feel sick.",
    "I was charged twice for the same order.",
    "Can I book a table for four tonight?",
    "I need to cancel my reservation.",
    "Does the pasta contain peanuts?",
    "My coupon code is not working.",
    "I lost my wallet at your restaurant.",
    "Can I speak with a human agent?"
]

for query in sample_queries:
    print(predict_intent(query))

"""## 14. Department Mapping for Routing

Intent classification is the first step.  
After predicting the intent, the chatbot can route the request to the correct department.
"""

INTENT_TO_DEPARTMENT = {
    "ORDER_STATUS": "Customer Support",
    "ORDER_DELAYED": "Delivery / Kitchen",
    "ORDER_NOT_RECEIVED": "Delivery",
    "MISSING_ITEM": "Kitchen / Takeout",
    "WRONG_ITEM": "Kitchen",
    "FOOD_QUALITY_ISSUE": "Food Quality",
    "FOOD_SAFETY_ISSUE": "Food Safety",
    "PAYMENT_FAILED": "Payments",
    "DOUBLE_CHARGED": "Payments",
    "REFUND_REQUEST": "Refunds",
    "RESERVATION_CREATE": "Reservations",
    "RESERVATION_MODIFY": "Reservations",
    "RESERVATION_CANCEL": "Reservations",
    "MENU_INQUIRY": "Menu",
    "ALLERGY_INQUIRY": "Menu / Food Safety",
    "PROMO_CODE_ISSUE": "Promotions",
    "LOYALTY_POINTS_ISSUE": "Loyalty",
    "STAFF_COMPLAINT": "Store Manager",
    "CLEANLINESS_COMPLAINT": "Cleaning / Store Manager",
    "LOST_AND_FOUND": "Front Desk",
    "CATERING_INQUIRY": "Catering",
    "HUMAN_AGENT_REQUEST": "Customer Support",
    "GENERAL_INQUIRY": "Customer Support",
    "OUT_OF_SCOPE": "No ticket / fallback"
}

def predict_intent_with_department(statement: str, model=None):
    result = predict_intent(statement, model=model)
    result["department"] = INTENT_TO_DEPARTMENT.get(result["predicted_intent"], "Unknown")
    return result

predict_intent_with_department("I got the wrong burger in my order.")

"""## 15. How to Load the `.pkl` Model in Production

Use this in FastAPI, Flask, LangGraph, or a backend service.
"""

# Example production loading code

loaded_model = joblib.load(best_model_path)

incoming_customer_message = "My order has not arrived yet."
predicted_intent = loaded_model.predict([clean_text(incoming_customer_message)])[0]

print("Incoming message:", incoming_customer_message)
print("Predicted intent:", predicted_intent)
print("Department:", INTENT_TO_DEPARTMENT.get(predicted_intent))

"""## 16. Final Outcome

At the end of this notebook, you get:

| Artifact | Path |
|---|---|
| Best model pickle | `/mnt/data/restaurant_intent_model_artifacts/best_restaurant_intent_model.pkl` |
| Model metadata | `/mnt/data/restaurant_intent_model_artifacts/model_metadata.json` |
| Model comparison table | `/mnt/data/restaurant_intent_model_artifacts/model_comparison.csv` |
| Candidate model pickles | `/mnt/data/restaurant_intent_model_artifacts/candidate_models/` |

The final model output is always:

```text
intent_code
```
"""