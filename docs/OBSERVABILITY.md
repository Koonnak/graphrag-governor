# Observability — GraphRAG‑Governor 📈

> **Goal:** Provide crystal‑clear guidance for **non‑technical** stakeholders (what we see and why it matters) and a deep **technical** playbook (how to instrument, scrape, trace, alert, and diagnose).

---

## 1) Executive Summary (Non‑Technical) 🎯

**What we see.** We continuously monitor **speed**, **reliability**, and **quality signals** from the AI system. Dashboards show if answers are fast, grounded, and cost‑efficient.

**Why it matters.**

* **Fewer surprises:** Early warning on slowdowns, error spikes, or model drifts.
* **Faster fixes:** Clear traces show where time is spent and where errors happen.
* **Accountability:** Metrics and evaluation scores are recorded for audits and trend analysis.

**Where to look.**

* **Grafana** for dashboards (latency, throughput, errors, A/B comparisons).
* **Jaeger** for deep‑dive request timelines (traces/spans).
* **Prometheus** for raw metrics and alerting rules.
* **MLflow** for evaluation runs and quality metrics.

---

## 2) Technical Overview (Telemetry Model) 🧠

**Signals**

* **Traces** (Jaeger): span hierarchy for `/query` pipeline: `http_query → retrieve → gather_contexts → generate`.
* **Metrics** (Prometheus): counters and histograms for throughput and latency.
* **(Optional) Logs:** structured logs aligned with `trace_id` / `span_id` (add a log collector if desired).

**Data path**

```
FastAPI (OTel SDK) ──OTLP gRPC──▶ OTel Collector ──▶ Jaeger (traces)
                                         └─▶ Prometheus (metrics) ──▶ Grafana (dashboards)
```

**Key design rules**

* **Stable names:** keep metric names and span names stable across versions.
* **Low cardinality:** prefer a small set of labels; avoid per‑user/per‑doc labels.
* **Fail‑open:** if the collector is down, the API still serves requests (no‑op exporters).

---

## 3) Metrics (Prometheus) 📊

We export business‑oriented and platform metrics via the OTel Collector’s Prometheus exporter.

### 3.1 Core metrics

* `rag_requests_total` (**Counter**)
  *Description:* Number of `/query` requests handled.
  *Labels:* none (keep cardinality low).
  *Usage:* throughput, error budget burn rates (when combined with HTTP error counters at the gateway).

* `rag_latency_ms` (**Histogram**)
  *Description:* End‑to‑end latency (ms) of the RAG pipeline per request.
  *Labels:* none.
  *Usage:* P50/P95 dashboards, SLO compliance.

> **Extend (optional):**
>
> * `rag_cost_usd` (**Summary/Histogram**) — estimated \$/request (requires token logging).
> * `retriever_cache_hit_ratio` (**Gauge**) — cache efficiency if a cache layer is added.
> * `rag_eval_faithfulness`, `rag_eval_relevancy` (**Gauge**) — export latest A/B eval results (sparingly; avoid high update rates).

### 3.2 Recording rules (examples)

```yaml
# recording.rules.yml
groups:
- name: graphrag-governor
  rules:
  - record: job:rag_latency_ms:p95
    expr: histogram_quantile(0.95, sum(rate(rag_latency_ms_bucket[5m])) by (le))
  - record: job:rag_latency_ms:p50
    expr: histogram_quantile(0.50, sum(rate(rag_latency_ms_bucket[5m])) by (le))
```

### 3.3 Alerting rules (sketch)

```yaml
# alerts.rules.yml
groups:
- name: graphrag-governor
  rules:
  - alert: HighLatencyP95
    expr: job:rag_latency_ms:p95 > 0.5   # seconds (adjust)
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "RAG p95 latency is elevated"
      description: "p95 latency above 500ms for 10m"

  - alert: ErrorRateHigh
    expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.01
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "HTTP 5xx rate > 1%"
      description: "Investigate API, retriever backends, or LLM provider"
```

> Adjust HTTP metric names to your gateway/exporter. Ensure your ingress emits `http_requests_total` with `status`.

---

## 4) Tracing (Jaeger) 🧵

**Span names**

* `http_query` — FastAPI request handling for `/query`.
* `retrieve` — BM25 or Dense search against the index.
* `gather_contexts` — Map document IDs to passages (I/O and CPU time).
* `generate` — Synthesis step (LLM call when a provider is configured).

**Attributes (examples)**

* `variant` (= `A` or `B`), `k` (top‑K), `latency_ms` (numeric).
* *(Optional)* `retriever.backend` (bm25|dense), `generator.provider` (openai|azure|hf|demo).

**Sampling**

* For local/debug: **always‑on** sampling is fine.
* For production: use **ParentBased + TraceIdRatio** (e.g., 10%) and keep error traces **always‑on**.

**Correlation**

* Honor W3C headers `traceparent`/`tracestate`.
* Propagate `X‑Request‑ID` for log correlation.
* Link MLflow run IDs as span attributes when running evaluations.

---

## 5) Dashboards (Grafana) 📊

**Recommended panels**

1. **Latency P50/P95** from `rag_latency_ms` (with annotations for deploys).
2. **Throughput** from `rag_requests_total` (rate).
3. **Error rate** from gateway `http_requests_total` (5xx / all).
4. **Variant comparison** — table/plots filtered by `variant` (via Jaeger search + Grafana panel links).
5. **Quality trend** — import MLflow metrics (faithfulness/relevancy) via datasource or periodic export.
6. **Resource overlays** — CPU/memory panels from node exporter (optional).

**UX tips**

* Use compact legends and consistent units (ms, req/s).
* Keep a top‑row SLO widget (p95 latency, error rate, availability).
* Link panels to Jaeger traces for drill‑down.

---

## 6) Prometheus & Collector Configuration ⚙️

**Collector (excerpt)** — already provided in the repo (`otel-collector-config.yaml`):

```yaml
receivers:
  otlp:
    protocols:
      grpc:
exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
processors:
  batch: {}
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

**Prometheus scrape** (`prometheus.yml` excerpt):

```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']
```

---

## 7) Privacy & Compliance 🔐

* **No raw PII** in metrics or labels; apply masking pre/post generation.
* **Minimize payloads** in traces; add only **IDs** or hashed tokens if needed.
* **Retention**: set Jaeger/Prometheus retention windows per policy (e.g., 7–30 days).
* **Access control**: restrict Grafana/Jaeger/Prometheus UIs to internal users.

---

## 8) Multi‑Tenancy & Naming 🏷️

* Set `service.name` via env (`SERVICE_NAME`) to separate environments (e.g., `graphrag‑governor‑dev/prod`).
* Avoid high‑cardinality labels like `user_id` or `doc_id` on metrics; keep them in traces if necessary.
* For per‑tenant views, maintain separate Grafana folders/datasources or label on the **trace**, not the **metric**.

---

## 9) SLOs & Error Budget 🧮

**Example SLOs**

* **Availability:** 99.9% monthly.
* **Latency:** p95 ≤ 500 ms for `/query`.
* **Error rate:** < 1% 5xx.

**Error budget math**

* At 99.9% availability, your monthly error budget is \~43 minutes of downtime.
* Use burn‑rate alerts (e.g., 14d/1h windows) to catch fast/slow burns.

---

## 10) Performance Testing 🚦

* Use k6/Locust to simulate traffic at realistic QPS.
* Observe `rag_latency_ms` histograms, p95 under load, and error rate.
* Compare Variant A/B under identical loads; tune `k` and caches accordingly.

---

## 11) Troubleshooting 🔧

* **No metrics in Grafana:** check Prometheus target health; verify Collector `prometheus` exporter and port `8889`.
* **No traces in Jaeger:** verify OTLP gRPC endpoint; ensure sampling isn’t filtering everything.
* **Latency spikes:** check retriever backend health, index size, `k` value, and CPU saturation.
* **HTTP 5xx:** inspect API logs, Jaeger spans; check LLM provider quotas/timeouts if enabled.

---

## 12) Roadmap 🔭

* Export **cost telemetry** (`rag_cost_usd`) and **cache metrics**.
* Add **re‑ranking spans** and **hybrid fusion** attributes.
* Integrate **logs** with trace IDs (e.g., Loki/ELK) for full‑stack correlation.
* Provide **Grafana dashboard JSON** as importable files.

