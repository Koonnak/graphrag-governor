#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight A/B latency evaluation for GraphRAG-Governor.

This script exercises the `/query` endpoint with multiple questions across
retrieval variants (e.g., A=BM25, B=Dense/FAISS) and produces *verifiable*
artifacts for credibility:
  - <out_dir>/<stamp>_quick_eval_summary.csv
  - <out_dir>/<stamp>_quick_eval_details.csv
  - <out_dir>/<stamp>_quick_eval_responses.jsonl

It prefers server-reported `latency_ms` (when present) and falls back to client
timing to ensure a result even if observability is misconfigured.

The goal is to provide a simple, reproducible *proof of execution* without
pretending to be a full quality harness (see docs/EVALUATION.md for RAGAS).

Usage:
  python scripts/quick_eval.py \
    --base-url http://localhost:8000 \
    --variants A B \
    --k 6 \
    --repeat 3 \
    --out-dir docs/artifacts

Requirements:
  - requests>=2.31
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import logging
import os
import statistics as stats
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import requests

# --------------------------- Data models -------------------------------------


@dataclasses.dataclass(frozen=True)
class RequestResult:
    """Container for a single request outcome."""

    ts_iso: str
    variant: str
    k: int
    question: str
    status_code: int
    ok: bool
    client_latency_ms: float
    server_latency_ms: Optional[float]
    answer_len: Optional[int]
    error: Optional[str]
    raw_response: Optional[Mapping[str, Any]]


@dataclasses.dataclass(frozen=True)
class VariantSummary:
    """Aggregate statistics for a given variant."""

    variant: str
    n: int
    ok_rate: float
    client_p50_ms: float
    client_p95_ms: float
    client_mean_ms: float
    server_p50_ms: Optional[float]
    server_p95_ms: Optional[float]
    server_mean_ms: Optional[float]


# --------------------------- Helpers -----------------------------------------


def now_iso() -> str:
    """Returns an ISO8601 timestamp (UTC) without microseconds."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def git_commit() -> Optional[str]:
    """Returns the short git commit hash if available, else None."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return None


def percentile(values: Sequence[float], pct: float) -> float:
    """Computes a percentile with linear interpolation.

    Args:
      values: Numeric sequence (non-empty).
      pct: Percentile in [0, 100].

    Returns:
      The interpolated percentile value.

    Raises:
      ValueError: If values is empty or pct out of range.
    """
    if not values:
        raise ValueError("percentile: empty values")
    if not (0.0 <= pct <= 100.0):
        raise ValueError("percentile: pct must be within [0, 100]")
    xs = sorted(values)
    if len(xs) == 1 or pct in (0.0, 100.0):
        idx = 0 if pct == 0.0 else len(xs) - 1
        return float(xs[idx])
    pos = (pct / 100.0) * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def robust_stats(values: Sequence[float]) -> Tuple[float, float, float]:
    """Returns (mean, p50, p95) for non-empty values."""
    mean = float(stats.fmean(values))
    p50 = percentile(values, 50.0)
    p95 = percentile(values, 95.0)
    return (mean, p50, p95)


def ensure_dir(path: Path) -> None:
    """Creates the directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def load_questions(path: Optional[Path]) -> List[str]:
    """Loads questions from a text file (one per line) or returns defaults.

    Args:
      path: Optional file path to a list of questions.

    Returns:
      List of questions (non-empty).
    """
    default_questions = [
        "What privacy guarantees do you provide?",
        "How does the architecture work?",
        "Explain the observability setup.",
        "What evaluation metrics are used and how are they logged?",
    ]
    if path is None:
        return default_questions
    text = path.read_text(encoding="utf-8")
    qs = [line.strip() for line in text.splitlines() if line.strip()]
    return qs or default_questions


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    params: Optional[Mapping[str, Any]] = None,
    json_body: Optional[Mapping[str, Any]] = None,
    timeout: float = 20.0,
    max_retries: int = 2,
    backoff_sec: float = 0.5,
) -> requests.Response:
    """Performs an HTTP request with simple retries and exponential backoff.

    Args:
      session: Reusable requests session.
      method: HTTP method (e.g., 'POST').
      url: Target URL.
      headers: Optional headers.
      params: Optional query params.
      json_body: Optional JSON body.
      timeout: Per attempt timeout in seconds.
      max_retries: Number of retry attempts on failure.
      backoff_sec: Initial backoff; doubles each retry.

    Returns:
      The final requests.Response (may be non-2xx).
    """
    attempt = 0
    last_exc: Optional[Exception] = None
    while attempt <= max_retries:
        try:
            return session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=timeout,
            )
        except Exception as exc:  # network or timeout
            last_exc = exc
            if attempt == max_retries:
                raise
            sleep_for = backoff_sec * (2**attempt)
            logging.warning("Request failed (%s). Retrying in %.2fs...", exc.__class__.__name__, sleep_for)
            time.sleep(sleep_for)
            attempt += 1
    # Should not reach here; keep type checker happy.
    if last_exc:
        raise last_exc
    raise RuntimeError("request_with_retry: reached unexpected control path")


def run_one_query(
    session: requests.Session,
    base_url: str,
    variant: str,
    k: int,
    question: str,
    timeout: float,
) -> RequestResult:
    """Runs a single /query call and captures robust timing/outputs.

    Args:
      session: Shared requests.Session.
      base_url: Base API URL, e.g., http://localhost:8000
      variant: 'A' or 'B'
      k: Top-K docs.
      question: Natural-language question.
      timeout: Request timeout in seconds.

    Returns:
      RequestResult with success flag, latencies, and raw JSON (if any).
    """
    url = f"{base_url.rstrip('/')}/query"
    params = {"variant": variant, "k": k}
    body = {"question": question}

    t0 = time.perf_counter()
    try:
        resp = request_with_retry(
            session,
            "POST",
            url,
            params=params,
            json_body=body,
            timeout=timeout,
            max_retries=1,
        )
        client_latency_ms = (time.perf_counter() - t0) * 1000.0
        ok = 200 <= resp.status_code < 300
        raw: Optional[Dict[str, Any]] = None
        server_latency_ms: Optional[float] = None
        answer_len: Optional[int] = None
        err: Optional[str] = None

        if ok:
            try:
                raw = resp.json()
                server_latency_ms = float(raw.get("latency_ms")) if isinstance(raw.get("latency_ms"), (int, float)) else None
                answer = raw.get("answer")
                answer_len = len(answer) if isinstance(answer, str) else None
            except Exception as parse_exc:
                ok = False
                err = f"json_parse_error: {parse_exc}"
        else:
            err = f"http_{resp.status_code}"

        return RequestResult(
            ts_iso=now_iso(),
            variant=variant,
            k=k,
            question=question,
            status_code=resp.status_code,
            ok=ok,
            client_latency_ms=float(client_latency_ms),
            server_latency_ms=server_latency_ms,
            answer_len=answer_len,
            error=err,
            raw_response=raw if ok else None,
        )
    except Exception as exc:
        client_latency_ms = (time.perf_counter() - t0) * 1000.0
        return RequestResult(
            ts_iso=now_iso(),
            variant=variant,
            k=k,
            question=question,
            status_code=-1,
            ok=False,
            client_latency_ms=float(client_latency_ms),
            server_latency_ms=None,
            answer_len=None,
            error=f"exception:{exc.__class__.__name__}",
            raw_response=None,
        )


def summarize_variant(results: Sequence[RequestResult], variant: str) -> VariantSummary:
    """Builds latency and success summary for a variant."""
    subset = [r for r in results if r.variant == variant]
    if not subset:
        return VariantSummary(variant, 0, 0.0, 0.0, 0.0, 0.0, None, None, None)
    ok_rate = sum(1 for r in subset if r.ok) / len(subset)

    client_vals = [r.client_latency_ms for r in subset if r.ok]
    client_mean, client_p50, client_p95 = robust_stats(client_vals) if client_vals else (0.0, 0.0, 0.0)

    server_vals = [r.server_latency_ms for r in subset if (r.ok and r.server_latency_ms is not None)]
    if server_vals:
        srv_mean, srv_p50, srv_p95 = robust_stats([float(v) for v in server_vals])  # type: ignore[arg-type]
    else:
        srv_mean = srv_p50 = srv_p95 = None  # type: ignore[assignment]

    return VariantSummary(
        variant=variant,
        n=len(subset),
        ok_rate=round(ok_rate, 4),
        client_p50_ms=round(client_p50, 2),
        client_p95_ms=round(client_p95, 2),
        client_mean_ms=round(client_mean, 2),
        server_p50_ms=None if srv_p50 is None else round(srv_p50, 2),
        server_p95_ms=None if srv_p95 is None else round(srv_p95, 2),
        server_mean_ms=None if srv_mean is None else round(srv_mean, 2),
    )


def write_artifacts(
    out_dir: Path,
    stamp: str,
    results: Sequence[RequestResult],
    commit: Optional[str],
    base_url: str,
) -> Tuple[Path, Path, Path]:
    """Writes summary CSV, details CSV, and JSONL responses.

    Args:
      out_dir: Target directory for artifacts.
      stamp: Timestamp used in filenames.
      results: All per-request results.
      commit: Git commit hash (optional).
      base_url: API base URL used for the run.

    Returns:
      Tuple of (summary_csv_path, details_csv_path, responses_jsonl_path).
    """
    ensure_dir(out_dir)
    summary_path = out_dir / f"{stamp}_quick_eval_summary.csv"
    details_path = out_dir / f"{stamp}_quick_eval_details.csv"
    jsonl_path = out_dir / f"{stamp}_quick_eval_responses.jsonl"

    # Per-variant summary
    variants = sorted({r.variant for r in results})
    rows_sum: List[Dict[str, Any]] = []
    for v in variants:
        s = summarize_variant(results, v)
        rows_sum.append(
            {
                "variant": s.variant,
                "n": s.n,
                "ok_rate": s.ok_rate,
                "client_mean_ms": s.client_mean_ms,
                "client_p50_ms": s.client_p50_ms,
                "client_p95_ms": s.client_p95_ms,
                "server_mean_ms": s.server_mean_ms,
                "server_p50_ms": s.server_p50_ms,
                "server_p95_ms": s.server_p95_ms,
                "git_commit": commit or "",
                "base_url": base_url,
                "stamp": stamp,
            }
        )
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "variant",
                "n",
                "ok_rate",
                "client_mean_ms",
                "client_p50_ms",
                "client_p95_ms",
                "server_mean_ms",
                "server_p50_ms",
                "server_p95_ms",
                "git_commit",
                "base_url",
                "stamp",
            ],
        )
        writer.writeheader()
        writer.writerows(rows_sum)

    # Per-request details
    with details_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ts_iso",
                "variant",
                "k",
                "question",
                "status_code",
                "ok",
                "client_latency_ms",
                "server_latency_ms",
                "answer_len",
                "error",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "ts_iso": r.ts_iso,
                    "variant": r.variant,
                    "k": r.k,
                    "question": r.question,
                    "status_code": r.status_code,
                    "ok": r.ok,
                    "client_latency_ms": round(r.client_latency_ms, 2),
                    "server_latency_ms": "" if r.server_latency_ms is None else round(r.server_latency_ms, 2),
                    "answer_len": "" if r.answer_len is None else r.answer_len,
                    "error": r.error or "",
                }
            )

    # Raw responses (JSON Lines)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in results:
            rec = {
                "ts_iso": r.ts_iso,
                "variant": r.variant,
                "k": r.k,
                "question": r.question,
                "status_code": r.status_code,
                "ok": r.ok,
                "client_latency_ms": r.client_latency_ms,
                "server_latency_ms": r.server_latency_ms,
                "error": r.error,
                "response": r.raw_response,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return summary_path, details_path, jsonl_path


# --------------------------- CLI / Main --------------------------------------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments.

    Args:
      argv: Optional sequence of arguments (defaults to sys.argv).

    Returns:
      Parsed argparse.Namespace.
    """
    p = argparse.ArgumentParser(
        description="Quick evaluation runner for GraphRAG-Governor (A/B latency)."
    )
    p.add_argument("--base-url", default="http://localhost:8000", help="API base URL (default: %(default)s)")
    p.add_argument("--variants", nargs="+", default=["A", "B"], help="Retrieval variants to test (space-separated, e.g., A B)")
    p.add_argument("--k", type=int, default=6, help="Top-K documents to retrieve (default: %(default)s)")
    p.add_argument("--repeat", type=int, default=3, help="Repeat each question N times per variant (default: %(default)s)")
    p.add_argument(
        "--questions-file",
        type=Path,
        default=None,
        help="Optional path to a text file with one question per line.",
    )
    p.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds (default: %(default)s)")
    p.add_argument("--out-dir", type=Path, default=Path("docs/artifacts"), help="Directory for artifacts (default: %(default)s)")
    p.add_argument("--verbose", action="store_true", help="Enable info-level logging.")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    questions = load_questions(args.questions_file)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    commit = git_commit()

    results: List[RequestResult] = []
    session = requests.Session()

    logging.info("Starting quick eval | base_url=%s variants=%s k=%d repeat=%d", args.base_url, args.variants, args.k, args.repeat)

    try:
        for variant in args.variants:
            for q in questions:
                for _ in range(args.repeat):
                    r = run_one_query(
                        session=session,
                        base_url=args.base_url,
                        variant=variant,
                        k=args.k,
                        question=q,
                        timeout=args.timeout,
                    )
                    results.append(r)
                    # Minimal progress feedback without noisy logs.
                    sys.stdout.write("." if r.ok else "x")
                    sys.stdout.flush()
            sys.stdout.write(f" {variant}\n")
        sys.stdout.write("\n")
    except KeyboardInterrupt:
        print("\nInterrupted by user; writing partial results...")

    summary_path, details_path, jsonl_path = write_artifacts(
        out_dir=args.out_dir, stamp=stamp, results=results, commit=commit, base_url=args.base_url
    )

    # Human-readable end summary
    variants = sorted({r.variant for r in results})
    print("\n=== Quick Eval Summary ===")
    print(f"Commit: {commit or 'N/A'} | Base URL: {args.base_url} | Stamp: {stamp}")
    for v in variants:
        s = summarize_variant(results, v)
        print(
            f"Variant {v}: n={s.n} ok_rate={s.ok_rate:.2f} "
            f"client_ms[p50={s.client_p50_ms:.1f}, p95={s.client_p95_ms:.1f}, mean={s.client_mean_ms:.1f}] "
            f"server_ms[p50={s.server_p50_ms}, p95={s.server_p95_ms}, mean={s.server_mean_ms}]"
        )
    print(f"\nArtifacts:\n- {summary_path}\n- {details_path}\n- {jsonl_path}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
