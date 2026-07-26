# Feature 4: Restaurant Support Intent Classifier

## Status

Built as a standalone Streamlit application with trained model artifacts.

## What is implemented

The classifier converts free-text restaurant support messages into structured
routing decisions.

For each message it returns:

- One of 24 supported intent codes
- Prediction confidence when supported by the selected model
- Responsible department
- Recommended routing action
- Whether human escalation is required

High-risk categories such as food-safety issues, double charges, staff complaints,
cleanliness complaints, and explicit human-agent requests are flagged for
escalation.

## Streamlit pages

- Home / Overview
- Single Prediction
- Batch Prediction from a CSV file
- Model Metrics and algorithm comparison
- Filterable Intent Catalog
- Test / Adversarial Examples
- Admin Notes

Batch results can be downloaded after prediction.

## Model assets

The included best model is a word TF-IDF plus Complement Naive Bayes pipeline.
The repository also contains candidate model artifacts and model-comparison
metadata.

Reported training metadata:

- 36,000 examples
- 28,800 training rows
- 7,200 test rows
- 24 intent classes
- Accuracy: 1.000
- Macro F1: 1.000

## Main source files

- `restaurant_intent_streamlit_app/mlapp.py`
- `restaurant_intent_streamlit_app/artifacts/`
- `datasets/ml_model/restaurant_intent_multi_algorithm_training (1).py`

## How to run

```bash
pip install -r restaurant_intent_streamlit_app/requirements.txt
streamlit run restaurant_intent_streamlit_app/mlapp.py
```

## Current limitations

- The dataset is synthetic/templated, so the near-perfect offline scores should not
  be treated as production accuracy.
- Real customer messages, spelling errors, mixed intents, and out-of-scope messages
  require broader evaluation.
- The classifier is currently a separate Streamlit app and is not called by the
  FastAPI `/chat` endpoint.

