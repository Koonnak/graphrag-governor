"""Guardrail policy utilities for minimal PII masking.

This module provides a conservative, dependency-free PII masking helper and a
small policy engine with pre-/post-processing hooks. It is intentionally
limited to avoid over-matching and breaking answers. For production, prefer
explicit allow-lists and audited regexes, and extend patterns (e.g., IBAN,
phone) only after evaluation on real data.

Example:
  from src.guardrails.policy import PolicyEngine

  engine = PolicyEngine()
  safe_q = engine.pre_enforce("Email me at alice@example.com")
  # -> "Email me at [REDACTED]"

  safe_a = engine.post_enforce("Contact: 4111111111111111")
  # -> "Contact: [REDACTED]"
"""
from __future__ import annotations

import re
from typing import Iterable


# Minimal patterns (intentionally conservative; avoid over-matching)
PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{13,16}\b"),                 # simplistic card-like numbers
    re.compile(r"\b\w+@\w+\.[A-Za-z]{2,}\b"),     # basic emails
]


def mask_pii(text: str, patterns: Iterable[re.Pattern[str]] = PII_PATTERNS) -> str:
    """Mask known PII occurrences within a string.

    Applies each regex pattern sequentially and replaces matches with
    the placeholder "[REDACTED]". Designed to be conservative and fast.

    Args:
      text: Input text possibly containing PII.
      patterns: Iterable of compiled regex patterns to apply. Defaults to
        `PII_PATTERNS`.

    Returns:
      The input text with all pattern matches replaced by "[REDACTED]".

    Examples:
      >>> mask_pii("Card: 4111111111111111")
      'Card: [REDACTED]'
      >>> mask_pii("alice@example.com")
      '[REDACTED]'
    """
    out = text
    for p in patterns:
        out = p.sub("[REDACTED]", out)
    return out


class PolicyEngine:
    """Hookable guardrail pipeline for pre-/post-processing.

    This tiny policy layer demonstrates how to enforce basic hygiene around
    user questions and LLM outputs. In a production setting, consider adding:
      * content policies (toxicity, safety),
      * attribution checks (faithfulness),
      * allow-lists / deny-lists for domains or patterns,
      * structured logging of decisions for audits.

    Attributes:
      allow_llm_judge: Whether an upstream LLM-as-judge step would be allowed
        (placeholder flag; not used in this demo policy).

    """

    def __init__(self, allow_llm_judge: bool = True) -> None:
        """Initialize the policy engine.

        Args:
          allow_llm_judge: Enables/disables optional LLM-as-judge logic
            (not implemented in this minimal demo).
        """
        self.allow_llm_judge = allow_llm_judge

    def pre_enforce(self, question: str) -> str:
        """Apply policies before retrieval/generation.

        Currently masks user-provided PII to reduce leakage risk when logging
        or sending the question downstream.

        Args:
          question: Raw user question.

        Returns:
          The sanitized question with basic PII masked.

        Examples:
          >>> PolicyEngine().pre_enforce("Mail me: bob@example.com")
          'Mail me: [REDACTED]'
        """
        return mask_pii(question)

    def post_enforce(self, answer: str) -> str:
        """Apply policies after generation.

        Currently masks any PII that might have been echoed or synthesized in
        the model's answer.

        Args:
          answer: Model answer string.

        Returns:
          The sanitized answer with basic PII masked.

        Examples:
          >>> PolicyEngine().post_enforce("Card: 5555555555554444")
          'Card: [REDACTED]'
        """
        return mask_pii(answer)

