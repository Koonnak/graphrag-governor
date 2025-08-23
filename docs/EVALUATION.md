# Evaluation — GraphRAG‑Governor 🧪

> **Goal:** Make quality measurable and comparable. This guide serves **non‑technical** stakeholders (why it matters) and **technical** teams (how to run, log, and interpret rigorous evaluations).

---

## 1) Executive Summary (Non‑Technical) 🎯

**What we measure.** We score AI answers on **truthfulness**, **relevance**, and **evidence use**. We track **speed** and **cost** so you can choose the best trade‑off.

**Why it matters.**

* **Trust:** Fewer hallucinations when we reward answers grounded in retrieved passages.
* **Cost control:** Compare setups (A/B) to find the cheapest configuration that still hits your quality bar.
* **Accountability:** Results are versioned in MLflow for auditability and trend analysis.

**How decisions are made.** We set **quality thresholds** (e.g., Faithfulness ≥ 0.75) and test side‑by‑side. The winning configuration moves to production if it meets the thresholds and SLOs.

---

## 2) Technical Overview (What we evaluate) 🛠️

* **RAGAS metrics** (default):

  * **Faithfulness** 🙇‍♂️ — How well the answer is supported by retrieved evidence.
  * **Answer Relevancy** 🎯 — How well the answer addresses the question.
  * *(Extensions)* **Context Precision/Recall**, **Context Relevancy**, **Citation Accuracy**.
* **Operational signals** (from telemetry): **latency (P50/P95)**, **throughput**, **error rate**, optional **token/cost**.
* **Experiment knobs:** retrieval **Variant** (A=BM25, B=Dense), **top‑K**, and (roadmap) **re‑ranking**, **hybrid fusion**, **prompt template**.

---

## 3) Datasets & Splits 📚

* **Bootstrap (public):** Start with a small HF dataset to validate the plumbing.
* **Product dataset (recommended):** Curate `(question, gold_contexts, gold_answer)` pairs from your domain.
* **Splits:** `train/valid/test` or time‑based splits. Keep a **frozen validation slice** for regression tracking.
* **Sampling:** Use stratified sampling across intents (how‑to, definition, policy, etc.).

**Data hygiene checklist** ✅

* Remove near‑duplicates; guard against leakage (no gold answers in the retrieval corpus).
* Keep metadata: category, difficulty, last\_updated.
* Version datasets and store a manifest (commit hash, date, size).

---

## 4) Running an Evaluation (Code) ▶️

Use the built‑in runner to evaluate a pipeline and log to **MLflow**.

```python
from src.eval.eval_runner import run_eval
from src.pipelines.rag import RAGPipeline, Retriever

# Example: build a small in-memory pipeline
DOCS = ["Intro...", "Architecture...", "Privacy..."]
IDS = ["doc_0","doc_1","doc_2"]
pipe = RAGPipeline(Retriever(DOCS, IDS))

# Evaluate on a small HF slice (plumbing demo)
scores = run_eval(pipe, hf_dataset="explodinggradients/llm-preference-synthetic", size=50)
print(scores)  # {'faithfulness': 0.xx, 'answer_relevancy': 0.yy}
```

**CLI one‑liners**

```bash
# Variant A vs B (pseudo-example using query endpoint via HTTP)
http POST :8000/query variant==A k==6 question="Explain GDPR guarantees" > A.json
http POST :8000/query variant==B k==6 question="Explain GDPR guarantees" > B.json
```

---

## 5) MLflow Conventions 📈

* **Experiment:** `rag_eval`
* **Run names:** `variant-A`, `variant-B`, `rerank-on`, etc.
* **Params:** `variant`, `k`, `model_id`, `dataset_id`, `seed`, `rerank`
* **Metrics:** `faithfulness`, `answer_relevancy`, `latency_p95` (optional), `cost_usd` (optional)
* **Artifacts:**

  * `predictions.jsonl` — Rows with `{question, answer, contexts, scores?}`
  * `errors.jsonl` — Failures/timeouts.
  * Plots: score distributions, A/B deltas.

**Predictions JSONL schema**

```json
{"question": "...", "answer": "...", "contexts": ["...", "..."], "variant": "A", "k": 6}
```

---

## 6) Interpreting Scores 🧭

* **Faithfulness** is the first gate. If it’s low, fix retrieval (indexing, K, re‑rank) before tuning prompts.
* **Answer Relevancy** improves with better recall (higher K) but may hurt latency; use A/B to find the sweet spot.
* **Trade‑offs:** Overlay quality metrics with latency/cost to decide **production defaults**.

**Example acceptance policy**

* `faithfulness ≥ 0.75` AND `answer_relevancy ≥ 0.75` on the frozen validation slice.
* `P95 latency ≤ 500 ms` and `error rate < 1%`.

---

## 7) A/B Testing Methodology ⚖️

* **Within‑subject design:** Run **both variants** on the **same questions** to reduce variance.
* **Randomization:** Shuffle question order; fix `seed`.
* **Blocking:** Compare by intent/category to avoid confounding.
* **Statistics:** Bootstrap confidence intervals; paired tests for A/B deltas.
* **Reporting:**

  * Delta table: mean scores, 95% CI, effect size.
  * Risk notes: regressions, outliers, coverage gaps.

---

## 8) Error Analysis 🔬

* **Buckets:**

  * Missing evidence (retrieval miss).
  * Fabricated facts (faithfulness fail).
  * Partially relevant answers (relevancy fail).
  * Format/policy violations (guardrails fail).
* **Dig tools:** Inspect per‑item scores, spans, and the retrieved passages.
* **Actions:** Create **contrastive** training items; adjust `k`, add synonyms, improve chunking.

---

## 9) Extending Metrics 📐

* **Context Precision/Recall:** fraction of retrieved passages that are actually used / should have been used.
* **Citation Accuracy:** answer cites the correct passages/ids.
* **Helpfulness/Coherence:** LLM‑judge rubric with human spot checks.
* **Safety:** toxicity, PII leaks, policy violations (guardrail counters).

**Implementation hints**

* Log per‑passage attribution (doc\_id, span) to enable citation checks.
* Keep metric names stable; avoid high‑cardinality labels in Prometheus.

---

## 10) Governance & Thresholds 🧩

* Define **quality gates** by product area (policy answers may require higher faithfulness).
* Use **change management**: PRs must show A/B results on the frozen validation slice.
* Store **evaluation manifests** (dataset hash, config, code version) as artifacts.

---

## 11) Anti‑Patterns 🚫

* Evaluating only on synthetic data.
* Mixing datasets across runs and calling it A/B.
* Ignoring drift (dataset gets stale; corpus changes silently).
* Over‑indexing on a single metric; always balance with latency/cost.

---

## 12) Roadmap 🔭

* **Cross‑encoder re‑rank** integration.
* **Hybrid fusion** (lexical+dense) with weight tuning.
* **Online evaluation** with canary traffic + rollback.
* **RL Auto‑Tuner (PPO):** learn `(k, fusion weights, prompt templates)` from batched evaluations.

---

## 13) Quick Checklist ✅

* [x] Dataset frozen and versioned
* [x] A/B config documented (variant, k, seed)
* [x] Metrics logged to MLflow
* [x] Score deltas + 95% CI reported
* [x] Latency/cost plotted alongside quality
* [x] Action items filed from error analysis

