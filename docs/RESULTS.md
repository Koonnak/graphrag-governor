# Results — GraphRAG-Governor 🧪

> **SAMPLE REPORT — for layout preview only.**  
> Replace this file by running:
> ```
> python scripts/quick_eval.py --repeat 3 --k 6 --verbose
> python scripts/mk_results_md.py --write --plot
> ```

---

## 1) Executive Summary (Non-Technical) 🎯
We exercised the API and compared two retrieval variants:
- **A (BM25)** for lexical matching.
- **B (Dense/FAISS)** for semantic recall.
We recorded per-request latencies and captured trace/metric screenshots.

---

## 2) Run Context (Technical) 🧩
- **Endpoint:** `POST /query?variant=A|B&k=6`
- **Design:** within-subject A/B; 3 repeats per question
- **Questions:** general RAG queries (see Appendix A)
- **Artifacts dir:** `docs/artifacts/`
- **Commit:** SAMPLE
- **Run stamp:** SAMPLE

---

## 3) Results Summary 📊
> SAMPLE numbers — will be replaced by `*_quick_eval_summary.csv`.

| Variant | n | OK Rate | Client Mean (ms) | P50 (ms) | P95 (ms) | Server Mean (ms) | P50 | P95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 24 | 1.00 | 62.4 | 58.1 | 153.2 | 45.7 | 42.9 | 120.5 |
| B | 24 | 1.00 | 78.9 | 71.6 | 201.3 | 61.2 | 55.4 | 168.9 |

**Chart (sample):**  
![quick-eval-latency](assets/quick_eval_latency.png)

> **Interpretation:** A shows slightly lower latency; B trades a bit of latency for stronger semantic recall. Tail (P95) remains acceptable in this sample.

---

## 4) Evidence Pack (Screenshots) 🖼️
- API docs → `docs/assets/api-docs.png`
- Jaeger `/query` trace → `docs/assets/jaeger-trace.png`
- Grafana p95 panel → `docs/assets/grafana-latency.png`

---

## 5) Artifact Index 📦
- `docs/artifacts/<stamp>_quick_eval_summary.csv` — per-variant metrics
- `docs/artifacts/<stamp>_quick_eval_details.csv` — per-request rows
- `docs/artifacts/<stamp>_quick_eval_responses.jsonl` — raw responses

---

## 6) Reproduce 🔁
```bash
cp .env.example .env
docker compose up -d --build
python -m pip install requests matplotlib
python scripts/quick_eval.py --repeat 3 --k 6 --verbose
python scripts/mk_results_md.py --write --plot
