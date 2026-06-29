# app.py
# =============================================================================
# Restaurant Customer Support — Intent Classification Streamlit App
# -----------------------------------------------------------------------------
# Loads a trained intent-classification model (.pkl) and lets users/admins:
#   - run single predictions with confidence, department + routing action
#   - run batch predictions over an uploaded CSV
#   - inspect model-comparison metrics
#   - browse the intent catalog
#   - run messy/adversarial test examples
#   - read admin / deployment notes
#
# The model output is ALWAYS one of the 24 allowed intent codes.
#
# Run with:
#     pip install -r requirements.txt
#     streamlit run mlapp.py
# =============================================================================

import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# -----------------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Restaurant Intent Classifier",
    page_icon="🍽️",
    layout="wide",
)

# -----------------------------------------------------------------------------
# Paths — resolve artifacts relative to this file, with sensible fallbacks
# so the app runs whether artifacts live in ./artifacts or in the original
# training output directory.
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
ARTIFACT_CANDIDATES = [
    HERE / "artifacts",
    HERE.parent / "datasets" / "restaurant_intent_model_artifacts",
]
ARTIFACT_DIR = next((p for p in ARTIFACT_CANDIDATES if p.exists()), ARTIFACT_CANDIDATES[0])

BEST_MODEL_PATH = ARTIFACT_DIR / "best_restaurant_intent_model.pkl"
METADATA_PATH = ARTIFACT_DIR / "model_metadata.json"
COMPARISON_PATH = ARTIFACT_DIR / "model_comparison.csv"
CANDIDATE_DIR = ARTIFACT_DIR / "candidate_models"


# =============================================================================
# DOMAIN KNOWLEDGE
# =============================================================================

# The 24 allowed intent codes. Predictions are constrained to this set.
ALLOWED_INTENTS = [
    "ORDER_STATUS", "ORDER_DELAYED", "ORDER_NOT_RECEIVED", "MISSING_ITEM",
    "WRONG_ITEM", "FOOD_QUALITY_ISSUE", "FOOD_SAFETY_ISSUE", "PAYMENT_FAILED",
    "DOUBLE_CHARGED", "REFUND_REQUEST", "RESERVATION_CREATE", "RESERVATION_MODIFY",
    "RESERVATION_CANCEL", "MENU_INQUIRY", "ALLERGY_INQUIRY", "PROMO_CODE_ISSUE",
    "LOYALTY_POINTS_ISSUE", "STAFF_COMPLAINT", "CLEANLINESS_COMPLAINT",
    "LOST_AND_FOUND", "CATERING_INQUIRY", "HUMAN_AGENT_REQUEST", "GENERAL_INQUIRY",
    "OUT_OF_SCOPE",
]

INTENT_MEANING = {
    "ORDER_STATUS": "Customer asking where their order is / status update",
    "ORDER_DELAYED": "Order is late / taking too long",
    "ORDER_NOT_RECEIVED": "Order never arrived",
    "MISSING_ITEM": "An item is missing from the order",
    "WRONG_ITEM": "Received the wrong item",
    "FOOD_QUALITY_ISSUE": "Food quality complaint (taste, temperature, freshness)",
    "FOOD_SAFETY_ISSUE": "Food safety problem (foreign object, illness)",
    "PAYMENT_FAILED": "Payment did not go through",
    "DOUBLE_CHARGED": "Charged more than once for the same order",
    "REFUND_REQUEST": "Customer requesting a refund",
    "RESERVATION_CREATE": "Create a new table reservation",
    "RESERVATION_MODIFY": "Change an existing reservation",
    "RESERVATION_CANCEL": "Cancel a reservation",
    "MENU_INQUIRY": "Questions about menu items / availability",
    "ALLERGY_INQUIRY": "Questions about allergens / ingredients",
    "PROMO_CODE_ISSUE": "Promo / coupon code not working",
    "LOYALTY_POINTS_ISSUE": "Loyalty points / rewards problem",
    "STAFF_COMPLAINT": "Complaint about staff behaviour",
    "CLEANLINESS_COMPLAINT": "Complaint about cleanliness / hygiene",
    "LOST_AND_FOUND": "Lost an item at the restaurant",
    "CATERING_INQUIRY": "Catering / large-order inquiry",
    "HUMAN_AGENT_REQUEST": "Customer explicitly wants a human agent",
    "GENERAL_INQUIRY": "General question not covered elsewhere",
    "OUT_OF_SCOPE": "Unrelated / out-of-scope message",
}

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
    "OUT_OF_SCOPE": "No ticket / fallback",
}

INTENT_TO_ROUTING_ACTION = {
    "ORDER_STATUS": "Call order status tool",
    "ORDER_DELAYED": "Check delivery/kitchen status and create delay ticket if needed",
    "ORDER_NOT_RECEIVED": "Create delivery escalation ticket",
    "MISSING_ITEM": "Create kitchen/takeout ticket",
    "WRONG_ITEM": "Create kitchen issue ticket",
    "FOOD_QUALITY_ISSUE": "Create food quality ticket",
    "FOOD_SAFETY_ISSUE": "Create critical food safety incident and escalate to human",
    "PAYMENT_FAILED": "Check payment status",
    "DOUBLE_CHARGED": "Check duplicate charge and route to payments",
    "REFUND_REQUEST": "Check refund eligibility",
    "RESERVATION_CREATE": "Create reservation",
    "RESERVATION_MODIFY": "Modify reservation",
    "RESERVATION_CANCEL": "Cancel reservation",
    "MENU_INQUIRY": "Search menu knowledge base",
    "ALLERGY_INQUIRY": "Search verified allergen data and escalate if uncertain",
    "PROMO_CODE_ISSUE": "Validate promo code",
    "LOYALTY_POINTS_ISSUE": "Check loyalty account",
    "STAFF_COMPLAINT": "Create store manager ticket",
    "CLEANLINESS_COMPLAINT": "Create cleaning/store manager ticket",
    "LOST_AND_FOUND": "Create lost and found case",
    "CATERING_INQUIRY": "Create catering lead",
    "HUMAN_AGENT_REQUEST": "Assign human support agent",
    "GENERAL_INQUIRY": "Search FAQ or ask clarification",
    "OUT_OF_SCOPE": "Show fallback response, no ticket by default",
}

# Intents that always warrant human review / escalation.
HIGH_RISK_INTENTS = {
    "FOOD_SAFETY_ISSUE",
    "DOUBLE_CHARGED",
    "STAFF_COMPLAINT",
    "CLEANLINESS_COMPLAINT",
    "HUMAN_AGENT_REQUEST",
}


# =============================================================================
# CORE FUNCTIONS (modular, cached)
# =============================================================================

@st.cache_resource(show_spinner="Loading model…")
def load_model(model_path: str = str(BEST_MODEL_PATH)):
    """Load a trained sklearn pipeline from a .pkl file (cached as a resource)."""
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    return joblib.load(path)


@st.cache_data(show_spinner=False)
def load_metadata() -> dict:
    """Load model_metadata.json. Returns {} if missing."""
    if not METADATA_PATH.exists():
        return {}
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_model_comparison() -> pd.DataFrame:
    """Load model_comparison.csv. Returns empty DataFrame if missing."""
    if not COMPARISON_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(COMPARISON_PATH)


def list_candidate_models() -> dict:
    """Map candidate model name -> .pkl path (if the directory exists)."""
    if not CANDIDATE_DIR.exists():
        return {}
    return {p.stem: p for p in sorted(CANDIDATE_DIR.glob("*.pkl"))}


def clean_text(text: str) -> str:
    """Light normalization matching the training pipeline."""
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _softmax(x: np.ndarray) -> np.ndarray:
    x = np.array(x, dtype=float)
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()


def get_department(intent: str) -> str:
    return INTENT_TO_DEPARTMENT.get(intent, "Unknown")


def get_routing_action(intent: str) -> str:
    return INTENT_TO_ROUTING_ACTION.get(intent, "Manual review")


def is_escalation_required(intent: str) -> bool:
    return intent in HIGH_RISK_INTENTS


def _confidence_for(model, cleaned: str):
    """Best-effort confidence: predict_proba, else decision_function, else None."""
    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba([cleaned])[0]
            return float(np.max(proba))
        except Exception:
            pass
    if hasattr(model, "decision_function"):
        try:
            scores = model.decision_function([cleaned])[0]
            if np.ndim(scores) == 0:
                return float(1 / (1 + np.exp(-scores)))
            return float(np.max(_softmax(scores)))
        except Exception:
            pass
    return None


def predict_intent(statement: str, model) -> dict:
    """Predict a single intent and assemble the full routing payload.

    The predicted_intent is constrained to the 24 allowed intent codes; any
    unexpected label falls back to OUT_OF_SCOPE.
    """
    cleaned = clean_text(statement)
    raw_pred = str(model.predict([cleaned])[0])
    predicted_intent = raw_pred if raw_pred in ALLOWED_INTENTS else "OUT_OF_SCOPE"
    confidence = _confidence_for(model, cleaned)

    return {
        "input_text": statement,
        "predicted_intent": predicted_intent,
        "confidence": confidence,
        "department": get_department(predicted_intent),
        "routing_action": get_routing_action(predicted_intent),
        "escalation_required": is_escalation_required(predicted_intent),
    }


def batch_predict(df: pd.DataFrame, model, text_col: str = "statement") -> pd.DataFrame:
    """Vectorized batch prediction over a DataFrame with a text column."""
    cleaned = df[text_col].astype(str).map(clean_text)
    preds = [p if p in ALLOWED_INTENTS else "OUT_OF_SCOPE"
             for p in map(str, model.predict(cleaned.tolist()))]

    # Confidence for the whole batch (best effort, vectorized where possible).
    confidences = [None] * len(df)
    if hasattr(model, "predict_proba"):
        try:
            confidences = list(np.max(model.predict_proba(cleaned.tolist()), axis=1))
        except Exception:
            confidences = [None] * len(df)
    elif hasattr(model, "decision_function"):
        try:
            scores = model.decision_function(cleaned.tolist())
            confidences = [float(np.max(_softmax(row))) for row in np.atleast_2d(scores)]
        except Exception:
            confidences = [None] * len(df)

    out = df.copy()
    out["predicted_intent"] = preds
    out["confidence"] = confidences
    out["department"] = [get_department(i) for i in preds]
    out["routing_action"] = [get_routing_action(i) for i in preds]
    out["escalation_required"] = [is_escalation_required(i) for i in preds]
    return out


def fmt_conf(conf) -> str:
    return "n/a" if conf is None else f"{conf:.1%}"


# =============================================================================
# SIDEBAR / NAVIGATION
# =============================================================================
st.sidebar.title("🍽️ Intent Classifier")

PAGES = [
    "Home / Overview",
    "Single Prediction",
    "Batch Prediction",
    "Model Metrics",
    "Intent Catalog",
    "Test / Adversarial",
    "Admin Notes",
]
page = st.sidebar.radio("Navigate", PAGES, label_visibility="collapsed")

# Surface a clear error if artifacts are missing, rather than crashing later.
st.sidebar.divider()
if BEST_MODEL_PATH.exists():
    st.sidebar.success(f"Model found:\n`{BEST_MODEL_PATH.name}`")
else:
    st.sidebar.error(
        f"Model not found in:\n`{ARTIFACT_DIR}`\n\n"
        "Place `best_restaurant_intent_model.pkl` in the artifacts folder."
    )
st.sidebar.caption(f"Artifacts: `{ARTIFACT_DIR}`")

metadata = load_metadata()
comparison = load_model_comparison()


def require_model():
    """Load the model or stop the page with a friendly error."""
    try:
        return load_model()
    except Exception as e:  # FileNotFoundError or unpickling error
        st.error(f"Could not load model: {e}")
        st.stop()


# =============================================================================
# PAGE 1 — HOME / OVERVIEW
# =============================================================================
if page == "Home / Overview":
    st.title("Restaurant Customer Support Intent Classifier")
    st.caption("Turn a raw customer message into a structured intent + routing decision.")

    st.markdown(
        """
        **Business problem.** Restaurant support teams receive thousands of free-text
        messages (late orders, refunds, reservations, complaints). Manually triaging
        them is slow and inconsistent.

        **Model goal.** Map each `customer message → intent_code`, then route it to the
        right department with a recommended action — escalating high-risk cases
        (food safety, double charges, staff/cleanliness complaints) to humans.
        """
    )

    best_name = metadata.get("best_model_name", "tfidf_complement_nb")
    n_rows = metadata.get("n_rows", 36000)
    n_train = metadata.get("n_train_rows", 28800)
    n_test = metadata.get("n_test_rows", 7200)
    n_classes = metadata.get("n_classes", 24)
    acc = metadata.get("accuracy", 1.0)
    f1 = metadata.get("macro_f1", 1.0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Examples", f"{n_rows:,}")
    c2.metric("Train / Test", f"{n_train:,} / {n_test:,}")
    c3.metric("Intent Classes", n_classes)
    c4.metric("Best Model Acc", f"{acc:.3f}")

    st.divider()
    st.subheader("Best Model Summary")
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Model", best_name)
    cc2.metric("Macro F1", f"{f1:.3f}")
    cc3.metric("Algorithm", "Complement NB + word TF-IDF")

    st.info(
        "The final output is always one of the **24 allowed intent codes** — never "
        "free-form text. See the **Intent Catalog** page for the full list."
    )


# =============================================================================
# PAGE 2 — SINGLE PREDICTION
# =============================================================================
elif page == "Single Prediction":
    st.title("Single Prediction")
    st.caption("Enter a customer message to get its intent, department, and routing action.")

    model = require_model()

    samples = [
        "— pick a sample —",
        "Where is my order?",
        "My pizza is 45 minutes late.",
        "I found hair in my food and feel sick.",
        "I was charged twice for the same order.",
        "Can I book a table for four tonight?",
        "I need to cancel my reservation.",
        "Does the pasta contain peanuts?",
        "My coupon code is not working.",
        "I lost my wallet at your restaurant.",
        "Can I speak with a human agent?",
    ]
    sample = st.selectbox("Sample messages", samples)
    default_text = "" if sample == samples[0] else sample
    message = st.text_area("Customer message", value=default_text, height=120,
                           placeholder="Type a customer message…")

    if st.button("Predict Intent", type="primary"):
        if not message.strip():
            st.warning("Please enter a message.")
        else:
            result = predict_intent(message, model)

            c1, c2, c3 = st.columns(3)
            c1.metric("Predicted Intent", result["predicted_intent"])
            c2.metric("Confidence", fmt_conf(result["confidence"]))
            c3.metric("Department", result["department"])

            st.write(f"**Routing action:** {result['routing_action']}")

            if result["escalation_required"]:
                st.error(
                    f"🚨 **High-risk intent — escalate to a human.** "
                    f"`{result['predicted_intent']}` requires human review."
                )
            else:
                st.success("✅ Standard handling — no mandatory human escalation.")

            if result["confidence"] is not None and result["confidence"] < 0.40:
                st.warning(
                    "⚠️ Low confidence prediction — consider asking the customer to "
                    "clarify or routing to a human agent."
                )

            with st.expander("Raw JSON output"):
                st.json(result)


# =============================================================================
# PAGE 3 — BATCH PREDICTION
# =============================================================================
elif page == "Batch Prediction":
    st.title("Batch Prediction")
    st.caption("Upload a CSV with a `statement` column to classify many messages at once.")

    model = require_model()
    uploaded = st.file_uploader("Upload CSV", type=["csv"])

    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            st.stop()

        if "statement" not in df.columns:
            st.error(
                f"CSV must contain a `statement` column. Found: {list(df.columns)}"
            )
        else:
            with st.spinner("Predicting…"):
                result_df = batch_predict(df, model, text_col="statement")

            st.success(f"Classified {len(result_df):,} rows.")

            # Quick summary of escalations + intent distribution.
            esc = int(result_df["escalation_required"].sum())
            c1, c2 = st.columns(2)
            c1.metric("Rows", f"{len(result_df):,}")
            c2.metric("Escalations Required", esc)

            st.dataframe(result_df, use_container_width=True, height=420)

            fig = px.bar(
                result_df["predicted_intent"].value_counts().reset_index(),
                x="predicted_intent", y="count",
                title="Predicted Intent Distribution",
            )
            st.plotly_chart(fig, use_container_width=True)

            csv_bytes = result_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download predictions CSV",
                data=csv_bytes,
                file_name="intent_predictions.csv",
                mime="text/csv",
            )
    else:
        st.info("Expected CSV format: a single column named `statement`.")
        st.code("statement\nWhere is my order?\nI was charged twice.\n", language="text")


# =============================================================================
# PAGE 4 — MODEL METRICS
# =============================================================================
elif page == "Model Metrics":
    st.title("Model Metrics")
    st.caption("Comparison of every candidate model trained during the experiment.")

    if comparison.empty:
        st.warning("`model_comparison.csv` not found in the artifacts folder.")
    else:
        df = comparison.copy()
        best_name = metadata.get("best_model_name") or df.sort_values(
            ["macro_f1", "accuracy"], ascending=False
        ).iloc[0]["model_name"]

        st.subheader("Comparison Table")
        st.dataframe(
            df.style.apply(
                lambda r: ["background-color: #1b5e20; color: white"
                           if r["model_name"] == best_name else "" for _ in r],
                axis=1,
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.success(f"🏆 Best model: **{best_name}**")

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.bar(df, x="model_name", y="accuracy", title="Accuracy by Model")
            fig.update_layout(xaxis_title="", xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.bar(df, x="model_name", y="macro_f1", title="Macro F1 by Model")
            fig.update_layout(xaxis_title="", xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)
        with col3:
            fig = px.bar(df, x="model_name", y="train_seconds", title="Train Time (s)")
            fig.update_layout(xaxis_title="", xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)

        st.warning(
            "⚠️ **Caveat:** Very high scores on synthetic data may indicate templated "
            "examples. Validate on messy real-world customer messages before production."
        )


# =============================================================================
# PAGE 5 — INTENT CATALOG
# =============================================================================
elif page == "Intent Catalog":
    st.title("Intent Catalog")
    st.caption("All 24 intent codes with meaning, department, routing action, and escalation flag.")

    catalog = pd.DataFrame({
        "intent_code": ALLOWED_INTENTS,
        "meaning": [INTENT_MEANING[i] for i in ALLOWED_INTENTS],
        "department": [get_department(i) for i in ALLOWED_INTENTS],
        "routing_action": [get_routing_action(i) for i in ALLOWED_INTENTS],
        "escalation_required": [is_escalation_required(i) for i in ALLOWED_INTENTS],
    })

    c1, c2 = st.columns(2)
    dept_filter = c1.selectbox(
        "Filter by department", ["All"] + sorted(catalog["department"].unique())
    )
    esc_filter = c2.selectbox("Filter by escalation", ["All", "Required", "Not required"])

    view = catalog
    if dept_filter != "All":
        view = view[view["department"] == dept_filter]
    if esc_filter == "Required":
        view = view[view["escalation_required"]]
    elif esc_filter == "Not required":
        view = view[~view["escalation_required"]]

    st.dataframe(view, use_container_width=True, hide_index=True, height=560)
    st.caption(f"Showing {len(view)} of {len(catalog)} intents.")


# =============================================================================
# PAGE 6 — TEST / ADVERSARIAL EXAMPLES
# =============================================================================
elif page == "Test / Adversarial":
    st.title("Test / Adversarial Examples")
    st.caption("Run messy, real-world-style messages to probe model robustness.")

    model = require_model()

    default_examples = [
        "yo where's my food it's been forever",
        "I paid twice for the same order",
        "there was hair in my pasta",
        "can I change my table booking to 8pm?",
        "my coupon does not work",
        "I left my wallet at your restaurant",
        "ur staff was super rude to me",
        "is the biryani spicy lol",
        "do u guys cater for 50 ppl",
        "gimme a human i'm done with this bot",
    ]
    text = st.text_area(
        "Test messages (one per line)",
        value="\n".join(default_examples),
        height=220,
    )

    if st.button("Run all test examples", type="primary"):
        messages = [m.strip() for m in text.splitlines() if m.strip()]
        if not messages:
            st.warning("Add at least one message.")
        else:
            rows = [predict_intent(m, model) for m in messages]
            result_df = pd.DataFrame(rows)
            result_df["confidence"] = result_df["confidence"].map(fmt_conf)
            st.dataframe(
                result_df[[
                    "input_text", "predicted_intent", "confidence",
                    "department", "routing_action", "escalation_required",
                ]],
                use_container_width=True,
                hide_index=True,
            )
            esc = int(pd.DataFrame(rows)["escalation_required"].sum())
            st.info(f"{esc} of {len(rows)} messages flagged for escalation.")


# =============================================================================
# PAGE 7 — ADMIN NOTES
# =============================================================================
elif page == "Admin Notes":
    st.title("Admin Notes")
    st.caption("Deployment guidance, limitations, and production checks.")

    st.subheader("Deployment guidance")
    st.markdown(
        """
        - The saved `.pkl` is a full sklearn **pipeline** (TF-IDF + classifier), so
          inference only needs the raw customer message.
        - Load once at startup and cache (`st.cache_resource` here; a module-level
          singleton in FastAPI/Flask).
        - Always map the predicted `intent_code` through the department + routing
          tables before acting.
        """
    )

    st.subheader("Limitations")
    st.markdown(
        """
        - Trained on **synthetic / templated** data — near-perfect offline scores do
          **not** guarantee real-world accuracy.
        - The model has no notion of conversation history or context beyond the single
          message.
        - Confidence from Naive Bayes can be poorly calibrated (over-confident).
        """
    )

    st.subheader("Recommended production checks")
    st.markdown(
        """
        1. **Validate with real conversations** before launch.
        2. **Monitor low-confidence predictions** and sample them for human review.
        3. **Force human review** for food-safety and payment (double-charge) issues.
        4. **Retrain with corrected examples** collected from production.
        5. **Log predictions and user feedback** for continuous evaluation.
        """
    )

    if metadata:
        with st.expander("Model metadata (model_metadata.json)"):
            st.json(metadata)

    cands = list_candidate_models()
    if cands:
        with st.expander(f"Candidate models on disk ({len(cands)})"):
            st.write(list(cands.keys()))
