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
  * **Hybrid fusion weight**: w ∈ \[0, 1] (roadmap)
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

  $$
  r_t = α·F + β·R − γ·\hat L − δ·\hat C − λ·P
  $$

  where F = faithfulness, R = relevancy, \hat L, \hat C are **normalized** latency/cost, and P is penalties (e.g., policy violations, instability).
* **Transition:** Apply new config, evaluate on a **validation slice**; observe scores.
* **Constraints:** Hard gates (minimum F/R), rollback on degradation.

---

## 4) Algorithm (PPO) 🤖

* **Why PPO:** Robust on mixed discrete/continuous actions, stable with KL‑regularization.
* **Action space:** Mixed (categorical for variant/template; discrete for k; Bernoulli for rerank; continuous for fusion weight).
* **Policy architecture:** MLP with separate heads per action type; shared encoder on state features.
* **Key hyperparameters:**

  * Rollout horizon: 1 episode = 1 batch evaluation (e.g., 100–500 queries)
  * γ (discount): 0.99; λ (GAE): 0.95
  * Clip ε: 0.2; KL target: 0.01–0.05; entropy bonus for exploration
  * Learning rate: 1e‑4 (schedule per KL); minibatches: 4–8; epochs: 3–10
* **Libraries:** Ray RLlib or CleanRL (preferred RLlib for distributed evaluation orchestration).

---

## 5) Data & Features 🧠

* **Evaluation datasets:** Frozen **validation slice** (representative, versioned). Optional **holdout test** for final checks.
* **State features:**

  * Aggregates: mean/median of F/R/latency/cost for last N batches
  * Category features (one‑hot) for question intent/domain
  * Corpus size, churn rate, embedding drift indicators (optional)
* **Normalization:** Robust scaling for latency/cost; cap outliers.

---

## 6) Safety & Governance 🛡️

* **Hard thresholds:** `faithfulness ≥ T_f`, `relevancy ≥ T_r`, `p95_latency ≤ T_l`.
* **Constrained optimization:** Reject actions violating gates; **Constrained PPO** variant (optional).
* **Rollback:** If performance regresses vs. baseline beyond δ, revert policy.
* **Auditability:** Log **all episodes** (config, scores, reward) to **MLflow** with artifacts.
* **Ethics/PII:** Guardrail counters in reward penalties (e.g., PII leak = heavy penalty).

---

## 7) Training Modes 🏋️

* **Offline (stage 1):** Replay **historical logs** / synthetic workloads. Fast iterations without user traffic.
* **Shadow (stage 2):** Run tuned configs in **shadow** alongside prod; compare on mirrored queries.
* **Canary (stage 3):** Route small traffic % (e.g., 5–10%) to the new policy; promote on success.

**Promotion criteria:**

* Reward ↑ with **95% CI** showing improvement
* No constraint violations for N consecutive batches
* Error budget (SLOs) respected

---

## 8) Evaluation Protocol 📏

* **A/B with paired design:** Same question set, controlled order, fixed seed.
* **Statistical checks:** Bootstrap CIs for deltas; paired t‑test/Wilcoxon where applicable.
* **Reporting:** Cost‑quality curve, Pareto frontier, per‑category breakdown, regression table.

---

## 9) Orchestration & Infra 🧱

* **Workers:** API pods for evaluation traffic; **queue** + **rate limiter** to avoid overload.
* **Coordinator:** RLlib Trainer managing rollouts and policy updates.
* **Storage:** MLflow for runs/artifacts; object store for large predictions; Prometheus for live metrics.
* **Configs as code:** YAML policy config (bounds, thresholds, reward weights).

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

## 10) API & Code Interfaces 🔌

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
    C = min(cost_usd / (gates.cost_ref or 1.0), 2.0)
    penalty = 0.0
    if F < gates.faithfulness or R < gates.relevancy:
        penalty += 1.0
    return w.alpha*F + w.beta*R - w.gamma*L - w.delta*C - w.lmbda*penalty
```

---

## 11) Risks & Mitigations ⚠️

* **Overfitting to the validation slice:** Rotate slices; cross‑validate; add temporal splits.
* **Instability / oscillation:** Conservative step sizes; KL control; early stopping.
* **Metric gaming:** Use multi‑metric reward; spot‑check with human review.
* **Cost spikes:** Budget guards; cap per‑episode cost; rate limit.

---

## 12) Deliverables & Milestones 📅

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

## 13) Glossary 📖

* **PPO:** Proximal Policy Optimization — policy‑gradient RL with clipped objective.
* **Episode:** One evaluation cycle (batch of queries).
* **Policy:** Mapping from state features to an action (configuration change).
* **Pareto frontier:** Set of non‑dominated configs balancing quality vs. cost/latency.

