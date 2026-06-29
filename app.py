# app.py
# =============================================================================
# Production RAG Quality Dashboard
# -----------------------------------------------------------------------------
# A single-file Streamlit application that monitors and compares multiple RAG
# retrieval methods using *dummy* / generated data only.
#
# No real databases, APIs, vector stores, or LLMs are contacted. Everything is
# generated in-code so the dashboard is fully runnable offline.
#
# Run with:
#     streamlit run app.py
# =============================================================================

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Production RAG Quality Dashboard",
    page_icon="🔎",
    layout="wide",
)

# Deterministic dummy data across reruns.
RNG = np.random.default_rng(42)


# =============================================================================
# DUMMY DATA LAYER
# All metrics below are fabricated to illustrate realistic RAG behaviour.
# =============================================================================

# Canonical method order (worst -> best) used throughout the app.
METHODS = [
    "Vector Top-5 (Baseline)",
    "Better Chunking + Top-K 20",
    "Metadata Filter + MMR",
    "Hybrid Search",
    "Hybrid + Rerank",
    "Best Production Method",
]

# Short labels for compact charts.
METHOD_SHORT = {
    "Vector Top-5 (Baseline)": "Baseline",
    "Better Chunking + Top-K 20": "Chunking+K20",
    "Metadata Filter + MMR": "Meta+MMR",
    "Hybrid Search": "Hybrid",
    "Hybrid + Rerank": "Hybrid+Rerank",
    "Best Production Method": "Best Prod",
}


@st.cache_data
def get_method_metrics() -> pd.DataFrame:
    """Per-method retrieval / answer-quality metrics (dummy)."""
    data = [
        # method, recall10, prec10, mrr, ndcg10, ctx_rel, faith, citation,
        #   halluc, no_info, dup_rate, toc_dom, latency_ms, cost_per_query
        ["Vector Top-5 (Baseline)",     0.41, 0.38, 0.45, 0.44, 0.42, 0.55, 0.40, 0.28, 0.31, 0.34, 0.46, 220, 0.0008],
        ["Better Chunking + Top-K 20",  0.58, 0.49, 0.57, 0.56, 0.55, 0.63, 0.52, 0.21, 0.20, 0.27, 0.33, 360, 0.0013],
        ["Metadata Filter + MMR",       0.66, 0.57, 0.64, 0.63, 0.62, 0.69, 0.61, 0.16, 0.15, 0.18, 0.19, 410, 0.0015],
        ["Hybrid Search",               0.74, 0.63, 0.71, 0.70, 0.69, 0.74, 0.68, 0.12, 0.11, 0.14, 0.15, 480, 0.0019],
        ["Hybrid + Rerank",             0.81, 0.74, 0.79, 0.78, 0.77, 0.82, 0.78, 0.08, 0.07, 0.09, 0.10, 640, 0.0026],
        ["Best Production Method",      0.89, 0.83, 0.87, 0.86, 0.86, 0.90, 0.88, 0.04, 0.03, 0.04, 0.05, 780, 0.0034],
    ]
    cols = [
        "Method", "Recall@10", "Precision@10", "MRR", "NDCG@10",
        "Context Relevance", "Faithfulness", "Citation Accuracy",
        "Hallucination Rate", "No-Info Response Rate", "Duplicate Result Rate",
        "TOC Dominance Rate", "Avg Latency (ms)", "Cost per Query ($)",
    ]
    df = pd.DataFrame(data, columns=cols)

    # Latency score: faster -> higher (normalised 0..1 against slowest method).
    max_lat = df["Avg Latency (ms)"].max()
    df["Latency Score"] = 1 - (df["Avg Latency (ms)"] / (max_lat * 1.15))

    # Weighted overall quality score (formula shown in Tab 9).
    df["Overall Quality Score"] = (
        0.20 * df["Recall@10"]
        + 0.15 * df["Precision@10"]
        + 0.15 * df["Faithfulness"]
        + 0.15 * df["Citation Accuracy"]
        + 0.10 * df["Context Relevance"]
        + 0.10 * (1 - df["No-Info Response Rate"])   # answer completeness proxy
        + 0.10 * (1 - df["Hallucination Rate"])
        + 0.05 * df["Latency Score"]
    ).round(3)

    return df


@st.cache_data
def get_pipeline_health() -> pd.DataFrame:
    """RAG pipeline stage health (dummy)."""
    rows = [
        ["Parsing / OCR", 55, "Yellow",
         "Loses slides, pages, tables, and headings",
         "Downstream chunks lack structure and context",
         "Use layout-aware parser; preserve page/slide/table/heading metadata"],
        ["Text Cleaning", 60, "Yellow",
         "Strips useful Unicode, bullets, URLs, punctuation",
         "Important tokens and references are lost",
         "Whitelist-based cleaning; keep bullets, URLs, and symbols"],
        ["Chunking", 45, "Red",
         "Small weak chunks with low overlap",
         "Fragmented embeddings; weak retrieval",
         "Semantic chunking ~1000-1500 chars, 150-200 overlap"],
        ["Embeddings", 65, "Yellow",
         "Embeds weak fragments and TOC/title chunks",
         "Vectors represent noise, not content",
         "Re-embed after better chunking; drop boilerplate"],
        ["Vector Store", 50, "Red",
         "Duplicates and non-deterministic chunk IDs",
         "Duplicate hits crowd out relevant content",
         "Deterministic chunk IDs + dedup on ingest"],
        ["Similarity Search", 48, "Red",
         "Top-k too small; no hybrid or metadata filter",
         "Low recall; TOC dominance",
         "Increase k, add BM25 hybrid + metadata filters + MMR"],
        ["Context Assembly", 52, "Yellow",
         "Not ordered, deduped, or grouped; no neighbor expansion",
         "Disjointed context; truncated answers",
         "Order, dedupe, group by doc; add neighbor expansion"],
        ["LLM Grounded Answer", 58, "Yellow",
         "Returns 'No information provided' on poor context",
         "Low answer completeness and trust",
         "Improve retrieval; add map-reduce summary path"],
    ]
    return pd.DataFrame(
        rows,
        columns=["Stage", "Health Score", "Status", "Main Problem",
                 "Consequence", "Recommended Fix"],
    )


@st.cache_data
def get_recall_at_k() -> pd.DataFrame:
    """Recall / precision at K per method (dummy), long format."""
    recall = {
        "Vector Top-5 (Baseline)":    [0.30, 0.36, 0.41, 0.44],
        "Better Chunking + Top-K 20": [0.42, 0.52, 0.58, 0.63],
        "Metadata Filter + MMR":      [0.50, 0.60, 0.66, 0.71],
        "Hybrid Search":              [0.58, 0.68, 0.74, 0.79],
        "Hybrid + Rerank":            [0.66, 0.76, 0.81, 0.85],
        "Best Production Method":     [0.74, 0.84, 0.89, 0.92],
    }
    ks = ["@5", "@10", "@20", "@50"]
    records = []
    for m, vals in recall.items():
        for k, v in zip(ks, vals):
            records.append({"Method": m, "K": k, "Recall": v})
    return pd.DataFrame(records)


@st.cache_data
def get_chunk_sizes() -> pd.DataFrame:
    """Two distributions of chunk sizes: weak (current) vs improved."""
    weak = RNG.normal(380, 160, 1500).clip(40, 1600)
    improved = RNG.normal(1200, 280, 1500).clip(300, 2200)
    df = pd.DataFrame({
        "Chunk Size (chars)": np.concatenate([weak, improved]),
        "Pipeline": (["Current (weak)"] * 1500) + (["Improved"] * 1500),
    })
    return df


@st.cache_data
def get_retrieval_heatmap() -> pd.DataFrame:
    """Method x retrieval-metric matrix (dummy) for a heatmap."""
    metrics = ["Hit@5", "Recall@5", "Recall@10", "Precision@5",
               "MRR", "NDCG@10", "Exact Match", "Meta Filter Success"]
    base = {
        "Vector Top-5 (Baseline)":    [0.40, 0.30, 0.36, 0.38, 0.45, 0.44, 0.30, 0.00],
        "Better Chunking + Top-K 20": [0.55, 0.42, 0.52, 0.49, 0.57, 0.56, 0.38, 0.00],
        "Metadata Filter + MMR":      [0.63, 0.50, 0.60, 0.57, 0.64, 0.63, 0.45, 0.82],
        "Hybrid Search":              [0.71, 0.58, 0.68, 0.63, 0.71, 0.70, 0.80, 0.60],
        "Hybrid + Rerank":            [0.79, 0.66, 0.76, 0.74, 0.79, 0.78, 0.84, 0.78],
        "Best Production Method":     [0.88, 0.74, 0.84, 0.83, 0.87, 0.86, 0.90, 0.93],
    }
    return pd.DataFrame(base, index=metrics).T  # rows=methods, cols=metrics


# =============================================================================
# SMALL UI HELPERS
# =============================================================================

def status_color(status: str) -> str:
    """Map a Green/Yellow/Red label to an emoji indicator."""
    return {"Green": "🟢 Green", "Yellow": "🟡 Yellow", "Red": "🔴 Red"}.get(status, status)


def style_health(df: pd.DataFrame):
    """Color the pipeline-health table by status."""
    def _row_style(row):
        color = {"Green": "#1b5e20", "Yellow": "#7a5d00", "Red": "#7a1f1f"}.get(row["Status"], "")
        return [f"background-color: {color}; color: white" if color else "" for _ in row]
    show = df.copy()
    show["Status"] = show["Status"].map(status_color)
    return show.style.apply(_row_style, axis=1)


def pct(x: float) -> str:
    return f"{x*100:.0f}%"


# =============================================================================
# SIDEBAR NAVIGATION
# =============================================================================
st.sidebar.title("🔎 RAG Dashboard")
st.sidebar.caption("Production RAG Quality — dummy data demo")

PAGES = [
    "1 · Executive Overview",
    "2 · RAG Pipeline Health",
    "3 · Method Comparison",
    "4 · Ingestion & Chunking Quality",
    "5 · Retrieval Quality",
    "6 · Reranking & Context Assembly",
    "7 · Answer Quality & Grounding",
    "8 · Failure Simulator",
    "9 · Best Method Recommendation",
    "10 · Implementation Roadmap",
]
page = st.sidebar.radio("Navigate", PAGES, label_visibility="collapsed")

st.sidebar.divider()
st.sidebar.info(
    "All numbers are **dummy/generated** for demonstration. "
    "No real data sources are queried."
)

# Shared dataframes.
methods_df = get_method_metrics()
best_method = methods_df.sort_values("Overall Quality Score", ascending=False).iloc[0]

st.title("Production RAG Quality Dashboard")


# =============================================================================
# TAB 1 — EXECUTIVE OVERVIEW
# =============================================================================
if page == PAGES[0]:
    st.subheader("Executive Overview")
    st.caption(
        "High-level health of the document Q&A RAG system: ingestion volume, "
        "index hygiene, retrieval success, and the currently recommended method."
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Documents", "1,284")
    c2.metric("Total Chunks", "96,420")
    c3.metric("Indexed Chunks", "91,830", "-4.8% not indexed")
    c4.metric("Duplicate Chunk Rate", "12.4%", "-needs dedup", delta_color="inverse")
    c5.metric("Avg Chunk Size", "1,180 chars")

    c6, c7, c8, c9, c10 = st.columns(5)
    c6.metric("Metadata Completeness", "71%")
    c7.metric("Retrieval Success Rate", "82%", "+6% vs baseline")
    c8.metric("No-Info Response Rate", "3%", "-28% vs baseline", delta_color="inverse")
    health_score = int(round(best_method["Overall Quality Score"] * 100))
    c9.metric("Overall RAG Health", f"{health_score}/100")
    c10.metric("Best Method", METHOD_SHORT[best_method["Method"]])

    st.divider()
    left, right = st.columns([2, 1])
    with left:
        fig = px.bar(
            methods_df.assign(Short=methods_df["Method"].map(METHOD_SHORT)),
            x="Short", y="Overall Quality Score",
            title="Overall Quality Score by Method",
            text="Overall Quality Score",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(xaxis_title="", yaxis_title="Quality Score")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.success(
            f"**Recommended:** {best_method['Method']}\n\n"
            f"Quality score **{best_method['Overall Quality Score']:.2f}**, "
            f"no-info rate **{pct(best_method['No-Info Response Rate'])}**, "
            f"hallucination **{pct(best_method['Hallucination Rate'])}**."
        )
        st.warning(
            "Top risks today: weak chunking, vector duplicates, and "
            "TOC/title chunks dominating retrieval."
        )


# =============================================================================
# TAB 2 — RAG PIPELINE HEALTH
# =============================================================================
elif page == PAGES[1]:
    st.subheader("RAG Pipeline Health")
    st.caption(
        "Stage-by-stage health of the pipeline: Parsing → Cleaning → Chunking → "
        "Embeddings → Vector Store → Search → Context Assembly → Grounded Answer."
    )

    health = get_pipeline_health()
    reds = (health["Status"] == "Red").sum()
    yellows = (health["Status"] == "Yellow").sum()
    greens = (health["Status"] == "Green").sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg Stage Health", f"{health['Health Score'].mean():.0f}/100")
    c2.metric("🔴 Critical Stages", reds)
    c3.metric("🟡 Needs Improvement", yellows)
    c4.metric("🟢 Healthy Stages", greens)

    st.dataframe(style_health(health), use_container_width=True, hide_index=True)

    fig = px.bar(
        health, x="Stage", y="Health Score", color="Status",
        color_discrete_map={"Green": "#2e7d32", "Yellow": "#f9a825", "Red": "#c62828"},
        title="Health Score by Pipeline Stage",
    )
    fig.update_layout(xaxis_title="", yaxis_range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB 3 — METHOD COMPARISON
# =============================================================================
elif page == PAGES[2]:
    st.subheader("Method Comparison")
    st.caption("Side-by-side comparison of all RAG methods across quality, cost, and latency metrics.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Methods Compared", len(methods_df))
    c2.metric("Best Quality", f"{methods_df['Overall Quality Score'].max():.2f}",
              METHOD_SHORT[best_method["Method"]])
    fastest = methods_df.loc[methods_df["Avg Latency (ms)"].idxmin()]
    c3.metric("Fastest Method", f"{fastest['Avg Latency (ms)']:.0f} ms",
              METHOD_SHORT[fastest["Method"]])
    c4.metric("Lowest Hallucination", pct(methods_df["Hallucination Rate"].min()))

    show = methods_df.copy()
    show.insert(0, "Short", show["Method"].map(METHOD_SHORT))
    st.dataframe(
        show.drop(columns=["Method"]).set_index("Short"),
        use_container_width=True,
    )

    colA, colB = st.columns(2)
    with colA:
        fig = px.bar(
            methods_df.assign(Short=methods_df["Method"].map(METHOD_SHORT)),
            x="Short", y="Overall Quality Score", text="Overall Quality Score",
            title="Overall Quality Score by Method",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        fig = px.scatter(
            methods_df.assign(Short=methods_df["Method"].map(METHOD_SHORT)),
            x="Avg Latency (ms)", y="Overall Quality Score",
            size="Cost per Query ($)", color="Short", text="Short",
            title="Latency vs Quality (bubble = cost/query)",
        )
        fig.update_traces(textposition="top center")
        st.plotly_chart(fig, use_container_width=True)

    # Radar chart for the best 3 methods.
    top3 = methods_df.sort_values("Overall Quality Score", ascending=False).head(3)
    radar_metrics = ["Recall@10", "Precision@10", "MRR", "NDCG@10",
                     "Faithfulness", "Citation Accuracy"]
    radar = go.Figure()
    for _, row in top3.iterrows():
        radar.add_trace(go.Scatterpolar(
            r=[row[m] for m in radar_metrics] + [row[radar_metrics[0]]],
            theta=radar_metrics + [radar_metrics[0]],
            fill="toself", name=METHOD_SHORT[row["Method"]],
        ))
    radar.update_layout(
        title="Top 3 Methods — Quality Profile",
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    )
    st.plotly_chart(radar, use_container_width=True)


# =============================================================================
# TAB 4 — INGESTION & CHUNKING QUALITY
# =============================================================================
elif page == PAGES[3]:
    st.subheader("Ingestion & Chunking Quality")
    st.caption("Quality of parsing, cleaning, and chunking — the foundation of retrieval quality.")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("OCR Success Rate", "88%")
    c2.metric("Structure Preservation", "54%", "-low", delta_color="inverse")
    c3.metric("Table Preservation", "41%", "-low", delta_color="inverse")
    c4.metric("Metadata Completeness", "71%")
    c5.metric("Avg Chunk Size", "1,180 chars")

    c6, c7, c8, c9, c10 = st.columns(5)
    c6.metric("Chunk Overlap", "165 chars")
    c7.metric("Too-Small Chunk Rate", "18%", delta_color="inverse")
    c8.metric("Too-Large Chunk Rate", "6%", delta_color="inverse")
    c9.metric("TOC Chunk Ratio", "9%", delta_color="inverse")
    c10.metric("Duplicate Chunk Rate", "12.4%", delta_color="inverse")

    st.divider()
    sizes = get_chunk_sizes()
    fig = px.histogram(
        sizes, x="Chunk Size (chars)", color="Pipeline", barmode="overlay",
        nbins=50, title="Chunk Size Distribution — Current vs Improved",
    )
    st.plotly_chart(fig, use_container_width=True)

    colA, colB = st.columns(2)
    with colA:
        by_type = pd.DataFrame({
            "Document Type": ["PDF (text)", "PDF (scanned)", "Slides", "Word", "HTML", "Spreadsheet"],
            "Chunk Quality": [0.78, 0.48, 0.52, 0.81, 0.74, 0.44],
        })
        fig = px.bar(by_type, x="Document Type", y="Chunk Quality",
                     title="Chunk Quality by Document Type", text="Chunk Quality")
        fig.update_traces(textposition="outside")
        fig.update_layout(yaxis_range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        improvement = pd.DataFrame({
            "Method": [METHOD_SHORT[m] for m in METHODS],
            "Chunk Quality": [0.45, 0.62, 0.68, 0.72, 0.80, 0.88],
        })
        fig = px.line(improvement, x="Method", y="Chunk Quality", markers=True,
                      title="Chunk Quality Improvement Across Methods")
        fig.update_layout(yaxis_range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB 5 — RETRIEVAL QUALITY
# =============================================================================
elif page == PAGES[4]:
    st.subheader("Retrieval Quality")
    st.caption("Recall, precision, ranking, and failure metrics per retrieval method.")

    sel = st.selectbox("Inspect a method", METHODS, index=len(METHODS) - 1)
    row = methods_df[methods_df["Method"] == sel].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Recall@10", f"{row['Recall@10']:.2f}")
    c2.metric("Precision@10", f"{row['Precision@10']:.2f}")
    c3.metric("MRR", f"{row['MRR']:.2f}")
    c4.metric("NDCG@10", f"{row['NDCG@10']:.2f}")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Empty Retrieval Rate", pct(row["No-Info Response Rate"]), delta_color="inverse")
    c6.metric("TOC Dominance Rate", pct(row["TOC Dominance Rate"]), delta_color="inverse")
    c7.metric("Duplicate Result Rate", pct(row["Duplicate Result Rate"]), delta_color="inverse")
    c8.metric("Context Relevance", f"{row['Context Relevance']:.2f}")

    st.divider()
    recall_df = get_recall_at_k()
    colA, colB = st.columns(2)
    with colA:
        fig = px.line(
            recall_df.assign(Short=recall_df["Method"].map(METHOD_SHORT)),
            x="K", y="Recall", color="Short", markers=True,
            title="Recall@K Comparison",
        )
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        # Precision@K derived as a damped fraction of recall for the demo.
        prec_df = recall_df.copy()
        prec_df["Precision"] = (recall_df["Recall"] * 0.9).round(3)
        fig = px.line(
            prec_df.assign(Short=prec_df["Method"].map(METHOD_SHORT)),
            x="K", y="Precision", color="Short", markers=True,
            title="Precision@K Comparison",
        )
        st.plotly_chart(fig, use_container_width=True)

    heat = get_retrieval_heatmap()
    fig = px.imshow(
        heat, text_auto=".2f", aspect="auto", color_continuous_scale="Blues",
        labels=dict(x="Metric", y="Method", color="Score"),
        y=[METHOD_SHORT[m] for m in heat.index],
        title="Method × Retrieval Metric Heatmap",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Top Failure Reasons")
    fails = pd.DataFrame({
        "Failure Reason": [
            "TOC/title chunk retrieved", "Top-k too small", "No exact keyword match",
            "Duplicate chunks crowd results", "Wrong document scope", "Fragmented chunk",
        ],
        "Share of Failures": [0.26, 0.21, 0.18, 0.14, 0.12, 0.09],
    })
    fig = px.bar(fails, x="Share of Failures", y="Failure Reason", orientation="h",
                 title="Top Retrieval Failure Reasons")
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB 6 — RERANKING & CONTEXT ASSEMBLY
# =============================================================================
elif page == PAGES[5]:
    st.subheader("Reranking & Context Assembly")
    st.caption("Impact of reranking, deduplication, neighbor expansion, and context ordering.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rerank Precision Gain", "+18%")
    c2.metric("Duplicate Removal Rate", "92%")
    c3.metric("Neighbor Expansion Coverage", "74%")
    c4.metric("Context Compression Ratio", "0.62")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Citation Coverage", "88%")
    c6.metric("Final Context Relevance", "0.86")
    c7.metric("Context Ordering Score", "0.83")
    c8.metric("Avg Context Chunks", "10")

    st.divider()
    colA, colB = st.columns(2)
    with colA:
        ba = pd.DataFrame({
            "Stage": ["Before Rerank", "After Rerank"],
            "Precision@10": [0.63, 0.83],
        })
        fig = px.bar(ba, x="Stage", y="Precision@10", text="Precision@10",
                     title="Precision Before vs After Reranking")
        fig.update_traces(textposition="outside")
        fig.update_layout(yaxis_range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        dup = pd.DataFrame({
            "Stage": ["Before Dedup", "After Dedup"],
            "Duplicate Rate": [0.31, 0.04],
        })
        fig = px.bar(dup, x="Stage", y="Duplicate Rate", text="Duplicate Rate",
                     title="Duplicate Rate Before vs After Dedup")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    ctx = pd.DataFrame({
        "Method": [METHOD_SHORT[m] for m in METHODS],
        "Context Quality": methods_df["Context Relevance"].tolist(),
    })
    fig = px.bar(ctx, x="Method", y="Context Quality", text="Context Quality",
                 title="Final Context Quality by Method")
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis_range=[0, 1])
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB 7 — ANSWER QUALITY & GROUNDING
# =============================================================================
elif page == PAGES[6]:
    st.subheader("Answer Quality & Grounding")
    st.caption("How faithful, grounded, complete, and well-cited the generated answers are.")

    best = best_method
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faithfulness", f"{best['Faithfulness']:.2f}")
    c2.metric("Groundedness", f"{best['Faithfulness'] - 0.02:.2f}")
    c3.metric("Answer Relevance", f"{best['Context Relevance']:.2f}")
    c4.metric("Answer Completeness", f"{1 - best['No-Info Response Rate']:.2f}")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Citation Accuracy", f"{best['Citation Accuracy']:.2f}")
    c6.metric("Hallucination Rate", pct(best["Hallucination Rate"]), delta_color="inverse")
    c7.metric("Unsupported Claim Rate", pct(best["Hallucination Rate"] + 0.02), delta_color="inverse")
    c8.metric("No-Info Response Rate", pct(best["No-Info Response Rate"]), delta_color="inverse")

    st.divider()
    short_df = methods_df.assign(Short=methods_df["Method"].map(METHOD_SHORT))
    colA, colB, colC = st.columns(3)
    with colA:
        fig = px.bar(short_df, x="Short", y="Faithfulness", text="Faithfulness",
                     title="Answer Faithfulness by Method")
        fig.update_traces(textposition="outside")
        fig.update_layout(xaxis_title="", yaxis_range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        fig = px.bar(short_df, x="Short", y="Hallucination Rate",
                     text="Hallucination Rate", title="Hallucination Rate by Method")
        fig.update_traces(textposition="outside", marker_color="#c62828")
        fig.update_layout(xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    with colC:
        fig = px.bar(short_df, x="Short", y="No-Info Response Rate",
                     text="No-Info Response Rate", title="No-Info Response Rate by Method")
        fig.update_traces(textposition="outside", marker_color="#f9a825")
        fig.update_layout(xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB 8 — FAILURE SIMULATOR
# =============================================================================
elif page == PAGES[7]:
    st.subheader("Failure Simulator")
    st.caption("Pick a query type and a method to see simulated retrieval behaviour, the likely "
               "failure, expected answer quality, and the recommended fix.")

    query_types = [
        "Simple lookup", "Deep lookup", "Follow-up", "Document summary",
        "Multi-document comparison", "Exact keyword query",
    ]
    sim_methods = [
        "Baseline", "Better Chunking", "Metadata + MMR",
        "Hybrid", "Hybrid + Rerank", "Best Production Method",
    ]

    c1, c2 = st.columns(2)
    qtype = c1.selectbox("Query type", query_types)
    smethod = c2.selectbox("RAG method", sim_methods, index=len(sim_methods) - 1)

    # Method capability score (0..1) used to gate which query types succeed.
    method_power = {
        "Baseline": 0.25, "Better Chunking": 0.45, "Metadata + MMR": 0.6,
        "Hybrid": 0.72, "Hybrid + Rerank": 0.82, "Best Production Method": 0.93,
    }
    # Difficulty of each query type (higher = needs a stronger method).
    query_difficulty = {
        "Simple lookup": 0.2, "Exact keyword query": 0.55, "Deep lookup": 0.6,
        "Follow-up": 0.7, "Document summary": 0.8, "Multi-document comparison": 0.88,
    }

    power = method_power[smethod]
    difficulty = query_difficulty[qtype]
    success = power >= difficulty

    # Simulated retrieved chunks (purely illustrative).
    if smethod == "Baseline":
        chunks = ["[TOC] Table of Contents", "[Title] Document Title Page",
                  "Intro paragraph (fragment)", "Section heading only",
                  "Short fragment (110 chars)"]
    elif smethod in ("Better Chunking", "Metadata + MMR"):
        chunks = ["Semantic chunk: policy overview", "Semantic chunk: scope & definitions",
                  "Section: implementation details", "Section: responsibilities",
                  "Appendix reference"]
    else:
        chunks = ["Hybrid hit: exact term match", "Vector hit: deep content",
                  "Reranked: most relevant passage", "Neighbor-expanded context (+/-1)",
                  "Doc-scoped chunk (metadata filter)", "Map-reduce summary segment"]

    # Failure reasons and fixes keyed by (query type, success).
    if not success:
        reason_map = {
            "Document summary": "Retrieved only top-k chunks; no map-reduce path, so summary is incomplete.",
            "Multi-document comparison": "Single-document bias; no cross-document retrieval or grouping.",
            "Follow-up": "No conversation-aware query rewrite; pronouns/context lost.",
            "Exact keyword query": "Vector-only search misses exact acronyms/section names (no BM25).",
            "Deep lookup": "Weak/small chunks and small top-k miss the deep passage.",
            "Simple lookup": "TOC/title chunks dominate; relevant chunk not retrieved.",
        }
        fix_map = {
            "Document summary": "Use document-summary route: fetch all chunks by doc_id + map-reduce.",
            "Multi-document comparison": "Enable multi-document retrieval + grouped, ordered context.",
            "Follow-up": "Add conversation-aware query rewriting before retrieval.",
            "Exact keyword query": "Add hybrid BM25 + vector search with Reciprocal Rank Fusion.",
            "Deep lookup": "Improve chunking (1000-1500 chars) and increase top-k; add reranking.",
            "Simple lookup": "Add metadata filtering + MMR; demote TOC/title chunks.",
        }
        reason = reason_map[qtype]
        fix = fix_map[qtype]
        quality = "❌ Poor — likely 'No information provided' or incomplete answer."
    else:
        reason = "No major failure — retrieval, reranking, and context assembly cover this query type."
        fix = "Maintain current configuration; monitor with regression tests."
        quality = "✅ Good — grounded, well-cited, complete answer expected."

    st.divider()
    st.markdown(f"**Scenario:** `{qtype}` × `{smethod}`")
    colL, colR = st.columns([1, 1])
    with colL:
        st.markdown("##### Simulated Retrieved Chunks")
        for i, ch in enumerate(chunks, 1):
            st.write(f"{i}. {ch}")
    with colR:
        st.metric("Method Capability", f"{power:.2f}")
        st.metric("Query Difficulty", f"{difficulty:.2f}")
        st.metric("Expected Outcome", "Success" if success else "Failure")

    if success:
        st.success(f"**Expected Answer Quality:** {quality}")
    else:
        st.error(f"**Failure Reason:** {reason}")
        st.warning(f"**Expected Answer Quality:** {quality}")
    st.info(f"**Recommended Fix:** {fix}")


# =============================================================================
# TAB 9 — BEST METHOD RECOMMENDATION
# =============================================================================
elif page == PAGES[8]:
    st.subheader("Best Method Recommendation")
    st.caption("The production-grade configuration recommended by the weighted scoring model.")

    st.success(
        "### 🏆 Best Method\n"
        "**Hybrid Search + Metadata Filtering + MMR + Cross-Encoder Reranking + "
        "Neighbor Expansion + Ordered Context Assembly + Map-Reduce Summary Path**"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall Quality", f"{best_method['Overall Quality Score']:.2f}")
    c2.metric("Recall@10", f"{best_method['Recall@10']:.2f}")
    c3.metric("Citation Accuracy", f"{best_method['Citation Accuracy']:.2f}")
    c4.metric("No-Info Rate", pct(best_method["No-Info Response Rate"]), delta_color="inverse")

    colA, colB = st.columns(2)
    with colA:
        st.markdown(
            "#### Why this method wins\n"
            "- Best **recall** and **precision**\n"
            "- Handles **exact keywords** (hybrid BM25 + vector)\n"
            "- Handles **document-specific** queries (metadata filters)\n"
            "- Handles **follow-ups** (query rewrite)\n"
            "- Handles **summaries** (map-reduce path)\n"
            "- Handles **multi-document** reasoning\n"
            "- Reduces **TOC dominance** (MMR + demotion)\n"
            "- Reduces **duplicate chunks** (dedup + deterministic IDs)\n"
            "- Improves **citation accuracy** and reduces 'No information provided'"
        )
    with colB:
        st.markdown("#### Weighted Scoring Formula")
        st.latex(
            r"""
            \begin{aligned}
            \text{score} =\ & 0.20\cdot \text{Recall@10} \\
            & + 0.15\cdot \text{Precision@10} \\
            & + 0.15\cdot \text{Faithfulness} \\
            & + 0.15\cdot \text{Citation Accuracy} \\
            & + 0.10\cdot \text{Context Relevance} \\
            & + 0.10\cdot \text{Answer Completeness} \\
            & + 0.10\cdot (1 - \text{Hallucination Rate}) \\
            & + 0.05\cdot \text{Latency Score}
            \end{aligned}
            """
        )

    st.divider()
    ranked = methods_df.sort_values("Overall Quality Score", ascending=False).copy()
    ranked["Short"] = ranked["Method"].map(METHOD_SHORT)
    fig = px.bar(ranked, x="Overall Quality Score", y="Short", orientation="h",
                 text="Overall Quality Score", title="Final Ranking by Weighted Score")
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB 10 — IMPLEMENTATION ROADMAP
# =============================================================================
elif page == PAGES[9]:
    st.subheader("Implementation Roadmap")
    st.caption("Phased plan to move from the weak baseline to the best production method.")

    phases = {
        "Phase 1 · Fix the Foundation": [
            "Fix parsing (layout-aware)",
            "Preserve slides / pages / headings / tables",
            "Improve cleaning (whitelist Unicode, bullets, URLs)",
            "Improve chunking (1000-1500 chars, 150-200 overlap)",
            "Re-ingest all documents",
        ],
        "Phase 2 · Improve Retrieval Breadth": [
            "Increase top-k",
            "Add metadata filtering (doc_id, section, tenant)",
            "Add MMR diversity",
            "Add neighbor chunk expansion",
        ],
        "Phase 3 · Hybrid + Reranking": [
            "Add hybrid BM25 + vector search (RRF)",
            "Add cross-encoder / LLM reranking",
            "Add ordered, deduplicated context assembly",
        ],
        "Phase 4 · Advanced Reasoning": [
            "Add map-reduce summaries",
            "Add multi-document retrieval",
            "Add follow-up query rewriting",
        ],
        "Phase 5 · Observability": [
            "Add evaluation dashboard",
            "Add RAG traces",
            "Add regression testing",
            "Add production monitoring",
        ],
    }

    cols = st.columns(len(phases))
    for col, (title, items) in zip(cols, phases.items()):
        with col:
            st.markdown(f"**{title}**")
            for it in items:
                st.markdown(f"- {it}")

    st.divider()
    timeline = pd.DataFrame({
        "Phase": list(phases.keys()),
        "Effort (weeks)": [3, 2, 3, 4, 2],
        "Expected Quality Gain": [0.15, 0.10, 0.18, 0.12, 0.05],
    })
    fig = px.bar(timeline, x="Phase", y="Expected Quality Gain",
                 text="Expected Quality Gain", color="Effort (weeks)",
                 color_continuous_scale="Tealgrn",
                 title="Expected Quality Gain by Phase")
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.caption("Run: `streamlit run app.py`")
