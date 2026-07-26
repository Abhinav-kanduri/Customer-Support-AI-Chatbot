# Feature 5: RAG Quality Analytics Dashboard

## Status

Built as an interactive Streamlit demonstration dashboard.

## What is implemented

The dashboard presents the major quality areas of a production
retrieval-augmented generation system.

It contains ten views:

1. Executive Overview
2. RAG Pipeline Health
3. Method Comparison
4. Ingestion and Chunking Quality
5. Retrieval Quality
6. Reranking and Context Assembly
7. Answer Quality and Grounding
8. Failure Simulator
9. Best Method Recommendation
10. Implementation Roadmap

The interface includes:

- RAG health and ingestion metrics
- Retrieval-method comparisons
- Chunk-size and retrieval-quality analysis
- Recall-at-K and heatmap visualizations
- Reranking and grounding views
- A simulator that compares query difficulty with method capability
- A recommended retrieval method based on the displayed quality scores

## Main source file

- `app.py`

## How to run

Install the Streamlit analytics dependencies if they are not already available,
then run:

```bash
streamlit run app.py
```

## Important data note

The current dashboard explicitly uses dummy/generated data for demonstration. It
does not query the live document database, vector index, chat responses, or
production monitoring system.

## Current limitations

- Metrics are illustrative rather than live production measurements.
- Dashboard recommendations are calculated from generated sample values.
- The dashboard is not currently integrated with the FastAPI backend or Supabase.
- Production use requires event logging, evaluation datasets, and live monitoring
  data sources.

