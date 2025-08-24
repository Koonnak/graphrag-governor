# RL Auto‑Tuner (PPO) — Roadmap 🔭

> **Purpose:** Define a rigorous plan to **automatically tune** GraphRAG‑Governor’s retrieval/generation stack using **Reinforcement Learning (PPO)**. Written for both **non‑technical** and **technical** audiences.

---

## 1) Executive Summary (Non‑Technical) 🎯

**What it is.** The RL Auto‑Tuner is an **autopilot** that experiments with system settings (e.g., how many passages to retrieve, which retriever to use, whether to re‑rank) and learns which combination gives the **best answers**, **fastest**, at the **lowest cost**.

**Why it matters.**

* **Better quality at lower cost:** Finds a sweet spot automatically, not by manual trial‑and‑error.
* **Adapts over time:** As content and questions change, the tuner relearns the best configuration.
* **Safe rollout:** Runs in a **shadow/canary** mode first; only promotes improvements with evidence.

**What success looks like.** A dashboard shows a **cost‑quality frontier** improving over releases (higher faithfulness/relevancy for the same or lower cost/latency).

---

## 2) Problem Statement & Objectives 🧩

* **Goal:** Maximize a **multi‑objective reward** combining **quality** (RAGAS faithfulness/relevancy) and **operational signals** (latency, cost), under **safety constraints** (no regressions beyond thresholds).
* **Decision variables (actions):**

  * Retrieval **variant**: {A=BM25, B=Dense}
  * **k** (top‑K): integer within \[3, 32]
  * **Re‑rank**: on/off (cross‑encoder; roadmap)
  * **Hybrid fusion weight**: w in \[0, 1] (roadmap)
  * **Prompt template id**: categorical (roadmap)

---

## 3) Formalization (MDP) 📐

* **State** `s_t` (features snapshot):

  * Recent **quality**: rolling means of faithfulness/relevancy
  * **Latency** stats (p50/p95), **cost** estimate
  * Current **config** (variant, k, rerank, fusion, prompt)
  * Corpus/update **metadata** (size, age), question **category**
* **Action** `a_t`: adjust config `(Δk, toggle rerank, switch variant/template, Δfusion)`
* **Reward** `r_t` (per batch):

  * `r_t = α·F + β·R − γ·L_hat − δ·C_hat − λ·P`
  * F = faithfulness, R = relevancy, L\_hat and C\_hat are normalized latency/cost, P is penalties (e.g., policy violations, instability).
* **Transition:** Apply new config, evaluate on a **validation slice**; observe scores.
* **Constraints:** Hard gates (minimum F/R), rollback on degradation.

---

## 4) Algorithm (PPO) 🤖

* **Why PPO:** Robust on mixed discrete/continuous actions, stable with KL‑regularization.
* **Action space:** Mixed (categorical for variant/template; discrete for k; Bernoulli for rerank; continuous for fusion weight).
* **Policy architecture:** MLP with separate heads per action type; shared encoder on state features.
* **Key hyperparameters:**

  * Rollout horizon: 1 episode = 1 batch evaluation (e.g., 100–500 queries)
  * gamma (discount): 0.99; lambda (GAE): 0.95
  * Clip epsilon: 0.2; KL target: 0.01–0.05; entropy bonus for exploration
  * Learning rate: 1e‑4 (schedule per KL); minibatches: 4–8; epochs: 3–10
* **Libraries:** Ray RLlib or CleanRL (preferred RLlib for distributed evaluation orchestration).

---

## 5) Prerequisites & Sizing 📦

**Hardware (minimum demo):** 4 vCPU, 8–16 GB RAM.
**GPU (optional):** speeds up embedding and re‑ranking; batch size 16–64.
**Traffic:** Evaluations run on *frozen* datasets; live canary gets ≤10% traffic.

**Software:** Python 3.11; RLlib/CleanRL; MLflow; Prometheus/Jaeger; Grafana; Neo4j.

---

## 6) Data & Datasets 🧠

* **Evaluation datasets:** Frozen **validation slice** (representative, versioned). Optional **holdout test** for final checks.
* **Schema:** `(question: str, gold_contexts: list[str]|None, gold_answer: str|None, category: str, last_updated: date)`
* **Manifest:** store `dataset_id`, commit hash, size, filters, and timestamp.
* **Hygiene:** deduplicate, guard against leakage (remove gold answers from retrieval corpus), stratify by category.

**Sample manifest (YAML)**

```yaml
id: acme-policies-v1
source: s3://datasets/acme/policies
commit: 9e1c3f0
size: 2000
splits:
  valid: 500
  test: 500
meta:
  categories: [policy, howto, definition]
  updated_at: 2025-08-01
```

---

## 7) State Features (Design) 🧾

| Feature                  | Type            | Source         | Notes                        |
| ------------------------ | --------------- | -------------- | ---------------------------- |
| `F_mean`, `R_mean`       | float           | RAGAS          | Rolling over last N episodes |
| `lat_p95`, `lat_p50`     | float           | Prometheus     | Normalize by targets         |
| `cost_usd`               | float           | Token logs     | Optional; per‑request avg    |
| `variant`, `k`, `rerank` | categorical/int | Config         | One‑hot/embedding            |
| `fusion_w`               | float           | Config         | \[0,1] clipped               |
| `category`               | categorical     | Dataset        | One‑hot/embedding            |
| `corpus_age_days`        | float           | Index metadata | Clamp to max                 |

**Normalization:** robust scaling; clip to \[−3σ, +3σ].

---

## 8) Reward & Constraints (Details) 🧮

**Scaling:**

* `L_hat = min(latency / T_l, 2.0)`
* `C_hat = min(cost / C_ref, 2.0)` (if cost available)

**Penalty P:**

* Policy violation (PII leak, toxicity) → +1.0
* Instability (std of scores above band) → +0.5

**Gates (hard):**

* `faithfulness ≥ 0.75` AND `relevancy ≥ 0.75`
* `p95_latency ≤ 500 ms`; error rate < 1%

**Ablations to run:** reward weights sweep; remove each feature head; discrete vs. continuous action formulations.

---

## 9) Training Modes 🏋️

* **Offline (stage 1):** Replay **historical logs** / synthetic workloads. Fast iterations without user traffic.
* **Shadow (stage 2):** Run tuned configs in **shadow** alongside prod; compare on mirrored queries.
* **Canary (stage 3):** Route small traffic % (e.g., 5–10%) to the new policy; promote on success.

**Promotion criteria:**

* Reward up with **95% CI** showing improvement
* No constraint violations for N consecutive batches
* Error budget (SLOs) respected

---

## 10) Orchestration & Infra 🧱

* **Workers:** API pods for evaluation traffic; **queue** + **rate limiter** to avoid overload.
* **Coordinator:** RLlib Trainer managing rollouts and policy updates.
* **Storage:** MLflow for runs/artifacts; object store for large predictions; Prometheus for live metrics.
* **Configs as code:** YAML policy config (bounds, thresholds, reward weights). Checked‑in under `configs/rl/`.

**Example policy config (YAML)**

```yaml
policy:
  bounds:
    k: {min: 3, max: 32}
    fusion_weight: {min: 0.0, max: 1.0}
  discrete:
    variant: [A, B]
    rerank: [off, on]
  thresholds:
    faithfulness: 0.75
    relevancy: 0.75
    p95_latency_ms: 500
  reward_weights:
    alpha: 0.5   # faithfulness
    beta: 0.5    # relevancy
    gamma: 0.2   # latency (penalty)
    delta: 0.2   # cost (penalty)
    lambda: 1.0  # policy/safety penalty multiplier
```

---

## 11) API & Code Interfaces 🔌

* **Internal service (suggested):** `POST /tuner/evaluate` — run a batch on a given config; returns F/R/latency/cost.
* **Artifacts:** Store `predictions.jsonl`, `contexts.jsonl`, summary CSV/plots.
* **MLflow schema:**

  * **Experiment:** `rl_autotuner`
  * **Run params:** variant, k, rerank, fusion\_weight, prompt\_id, dataset\_id, seed
  * **Metrics:** faithfulness, relevancy, p95\_latency, cost\_usd, reward

**Reward helper (pseudo‑code)**

```python
def compute_reward(F, R, lat_ms, cost_usd, gates, w):
    L = min(lat_ms / gates.p95_latency_ms, 2.0)   # normalize & cap
    C = min(cost_usd / (getattr(gates, 'cost_ref', 1.0)), 2.0)
    penalty = 0.0
    if F < gates.faithfulness or R < gates.relevancy:
        penalty += 1.0
    return w.alpha*F + w.beta*R - w.gamma*L - w.delta*C - w.lmbda*penalty
```

---

## 12) Statistics & OPE (Offline Policy Eval) 📊

* **Design:** within‑subject A/B; fixed seed; mirrored order.
* **CIs:** bootstrap 10k resamples; report mean delta and 95% CI.
* **Sequential testing:** use spending functions or fixed horizons to avoid peeking bias.
* **OPE:** Inverse Propensity Scoring (IPS), Doubly Robust (DR) when logged propensities are available.
* **Power analysis:** estimate required N to detect delta=+0.03 in faithfulness at 80% power.

---

## 13) Canary Runbook 🦜

1. Enable shadow mode; compare reward and gates for 3–5 episodes.
2. Promote to **5%** canary; add **burn‑rate** alerts (latency p95, error rate).
3. If green for 24–48h, increase to **25%**.
4. Full rollout when frontier improvement is stable and no SLO breach.

**Rollback policy:** immediate rollback on gate breach or burn‑rate alert; freeze policy and open incident.

---

## 14) Governance & Compliance 🛡️

* **Audit trail:** MLflow artifacts include policy config, dataset manifest, code commit.
* **Ethics:** penalize toxicity/PII leaks in reward; add human spot‑checks on flagged items.
* **Data retention:** align with org policy (e.g., 90‑day MLflow, 14–30 day telemetry).

---

## 15) Risks & Mitigations ⚠️

* **Overfitting to the validation slice:** Rotate slices; cross‑validate; add temporal splits.
* **Instability / oscillation:** Conservative step sizes; KL control; early stopping.
* **Metric gaming:** Use multi‑metric reward; spot‑check with human review.
* **Cost spikes:** Budget guards; cap per‑episode cost; rate limit.

---

## 16) Deliverables & Milestones 📅

1. **Spec & scaffolding** (this doc + config schema) ✅
2. **Offline simulator** with log‑replay and reward function ✅/🔜
3. **Shadow evaluator** service + MLflow logging 🔜
4. **PPO trainer** (RLlib) with mixed action space 🔜
5. **Canary rollout** with promotion gate 🔜
6. **Report**: Pareto frontier vs. manual baselines, ablations 🔜

**Success criteria**

* ≥ **+5–10%** reward vs. static baseline across 3 datasets
* No constraint violations; SLOs met

---

## 17) Dashboards for RL 📈

* **Policy performance:** reward per episode, moving average, gate breaches.
* **Quality vs. Cost:** scatter plot with Pareto frontier overlay.
* **Variant breakdown:** share of actions (A/B, rerank on/off) and their conditional returns.
* **Latency distribution:** p50/p95 by episode; overlays for canary vs. baseline.

---

## 18) Implementation Blueprint 🏗️

**Repo layout (additions):**

```
src/rl/
  __init__.py
  features.py        # state feature builders
  reward.py          # reward + penalties
  trainer.py         # PPO loop (RLlib)
  policy_config.py   # YAML load/validate
  evaluators/
    offline.py       # log replay
    shadow.py        # mirrored traffic
    canary.py        # % traffic routing
configs/rl/
  policy.defaults.yaml
```

**Open items:** CI job for offline simulator; nightly run on staging; export Grafana panels.

---

## 19) Glossary 📖

* **PPO:** Proximal Policy Optimization — policy‑gradient RL with clipped objective.
* **Episode:** One evaluation cycle (batch of queries).
* **Policy:** Mapping from state features to an action (configuration change).
* **Pareto frontier:** Set of non‑dominated configs balancing quality vs. cost/latency.
