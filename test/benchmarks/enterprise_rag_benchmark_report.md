# EnterpriseRAG-Bench Scaled Evaluation Report
**Date:** 2026-11-07 03:51:30
**Corpus Size:** 80 Enterprise Documents (61 Ground-Truth, 19 Distractors, ~215 Chunks)
**Benchmark Questions:** 28 Atomic Fact-Verified Enterprise Questions

## Overall Retrieval & Generation Performance

| Retrieval Mode | Avg Recall@5 | Fact Accuracy Score | Avg Latency (s) |
|---|:---:|:---:|:---:|
| **Vector Only** | 99.4% | 73.0% | 5.57s |
| **FTS Only** | 98.2% | 77.5% | 7.11s |
| **Hybrid (RRF)** | 96.3% | 75.1% | 4.81s |
| **Hybrid + Graph** | 96.3% | 77.4% | 12.06s |

## Per-Category Accuracy Breakdown

| Category | Questions | Vector Only | FTS Only | Hybrid (RRF) | Hybrid + Multi-Hop Graph | Graph Advantage |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **basic** | 5 | 95.0% | 95.0% | 100.0% | 100.0% | **+5.0%** |
| **completeness** | 5 | 52.4% | 53.2% | 55.0% | 56.6% | **+4.2%** |
| **conflicting_info** | 2 | 87.5% | 81.0% | 81.0% | 81.0% | -6.5% |
| **constrained** | 6 | 89.3% | 98.3% | 96.0% | 94.8% | **+5.5%** |
| **intra_document_reasoning** | 3 | 66.7% | 83.3% | 83.3% | 83.3% | **+16.6%** |
| **project_related** | 3 | 29.7% | 36.3% | 41.3% | 34.7% | **+5.0%** |
| **semantic** | 4 | 77.0% | 79.7% | 54.0% | 75.0% | -2.0% |

---
