---
name: "🐞 Bug report (GraphRAG-Governor)"
description: Report a reproducible defect with clear evidence (traces, metrics, artifacts)
title: "[BUG] <Area>: <Symptom>"
labels: ["bug", "needs-triage"]
assignees: []
---

<!--
Thank you! This template is optimized for fast, high-quality triage.
Please **sanitize PII/secrets** before posting (tokens, emails, payloads).
Attach **proof-of-execution** (Jaeger trace IDs, Prometheus/Grafana panels, CSV artifacts).
-->

## 1) Summary
**One–two sentences. What’s broken, where, and user impact?**  
<replace me>

**Severity (pick one):** Critical / High / Medium / Low  
**SLO impact:** p95 latency > target / error rate > target / availability drop / data issue  
**Component(s):** api | pipelines | retriever | guardrails | obs | eval | kg | docker | ci | docs

---

## 2) Affected Versions / Commits
- **Tag/Version:** <e.g., v0.1.0>
- **Commit SHA:** <e.g., a1b2c3d>
- **Branch:** <e.g., main>
- **First seen:** <date/timezone>
- **Regression from:** <tag/sha> (if known)

---

## 3) Environment
| Item | Value |
|---|---|
| OS / Distro | <e.g., macOS 14.5 / Ubuntu 22.04> |
| Hardware | <e.g., 8 vCPU / 16 GB RAM / no-GPU> |
| Python | <e.g., 3.11.7> |
| Docker / Compose | <e.g., 25.0.3 / v2.27.0> |
| `.env` deltas (no secrets) | <e.g., OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317> |
| Stack | `docker compose up -d --build` / custom |
| Default datasources | Prometheus OK / Grafana datasource set / Jaeger reachable |

**Sanitized outputs (optional but helpful):**
```bash
docker compose ps
docker --version && docker compose version
python --version
