# Restaurant Customer Support — Intent Classification App

A Streamlit web app that loads a trained intent-classification model and turns a raw
customer message into a structured decision:

```json
{
  "input_text": "I was charged twice for the same order.",
  "predicted_intent": "DOUBLE_CHARGED",
  "confidence": 0.99,
  "department": "Payments",
  "routing_action": "Check duplicate charge and route to payments",
  "escalation_required": true
}
```

The predicted intent is **always one of 24 allowed intent codes** — never free-form text.

## Features

| Page | What it does |
|---|---|
| **Home / Overview** | Project summary, dataset stats, best-model summary |
| **Single Prediction** | Classify one message; intent, confidence, department, routing, escalation |
| **Batch Prediction** | Upload a CSV (`statement` column), classify all rows, download results |
| **Model Metrics** | Model comparison table + accuracy / F1 / train-time charts |
| **Intent Catalog** | All 24 intents with meaning, department, routing, escalation; filterable |
| **Test / Adversarial** | Run messy real-world-style messages to probe robustness |
| **Admin Notes** | Deployment guidance, limitations, production checks |

## Project structure

```
restaurant_intent_streamlit_app/
├── mlapp.py
├── requirements.txt
├── README.md
└── artifacts/
    ├── best_restaurant_intent_model.pkl
    ├── model_metadata.json
    ├── model_comparison.csv
    └── candidate_models/
        ├── dummy_most_frequent.pkl
        ├── tfidf_multinomial_nb.pkl
        ├── tfidf_complement_nb.pkl
        ├── tfidf_logistic_regression.pkl
        ├── tfidf_linear_svc.pkl
        ├── tfidf_sgd_log_loss.pkl
        ├── char_tfidf_logistic_regression.pkl
        └── hybrid_word_char_logistic_regression.pkl
```

> The app resolves artifacts from `./artifacts` first, and falls back to
> `../datasets/restaurant_intent_model_artifacts` if that folder is missing — so it
> works both standalone and inside the original project layout.

## Model

- **Best model:** `tfidf_complement_nb` (Complement Naive Bayes + word TF-IDF)
- **Dataset:** 36,000 examples · 28,800 train / 7,200 test · 24 intent classes
- **Offline scores:** Accuracy 1.000 · Macro F1 1.000

> ⚠️ **Caveat:** these near-perfect scores come from synthetic/templated data.
> Validate on messy real-world customer messages before trusting them in production.

## Run

```bash
pip install -r requirements.txt
streamlit run mlapp.py
```

Then open the URL Streamlit prints (default http://localhost:8501).

## Batch CSV format

```csv
statement
Where is my order?
I was charged twice for the same order.
Does the pasta contain peanuts?
```

The app appends: `predicted_intent`, `confidence`, `department`, `routing_action`,
`escalation_required`.

## Production notes

- High-risk intents (`FOOD_SAFETY_ISSUE`, `DOUBLE_CHARGED`, `STAFF_COMPLAINT`,
  `CLEANLINESS_COMPLAINT`, `HUMAN_AGENT_REQUEST`) are flagged for human escalation.
- Monitor low-confidence predictions, log feedback, and retrain with corrected
  real-world examples.
