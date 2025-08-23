"""Centralized runtime configuration.

This module centralizes environment-backed settings for the application and
provides a thin validation layer. Keeping configuration in one place improves
testability, reduces duplication, and prevents accidental hard failures on
missing optional variables.

Notes:
  - Validation is lightweight: it guards common misconfigurations early.
  - Optional keys do not hard-fail; critical ones are sanity-checked.
  - Keep this module import-safe (avoid heavy imports and side effects).

Example:
  from src.config import settings
  uri = settings.NEO4J_URI
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable application settings.

    Attributes:
      LLM_MODEL: Name of the LLM to use (optional; demo uses a placeholder).
      LLM_API_BASE: Base URL of the LLM provider (optional).
      LLM_API_KEY: API key/token for the LLM provider (optional).

      OTEL_ENDPOINT: OTLP gRPC endpoint for the OpenTelemetry Collector.
      SERVICE_NAME: Logical service name used in traces/metrics.
      LOG_LEVEL: Application log level (DEBUG, INFO, WARN, or ERROR).

      NEO4J_URI: Connection string for Neo4j (bolt:// or neo4j://).
      NEO4J_USER: Neo4j username.
      NEO4J_PASSWORD: Neo4j password.

      MLFLOW_TRACKING_URI: MLflow tracking server URI.
    """

    # LLM (optional)
    LLM_MODEL: str | None
    LLM_API_BASE: str | None
    LLM_API_KEY: str | None

    # Observability
    OTEL_ENDPOINT: str
    SERVICE_NAME: str
    LOG_LEVEL: str

    # Graph store
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str

    # MLflow
    MLFLOW_TRACKING_URI: str

    def validate(self) -> "Settings":
        """Perform lightweight validation to catch common misconfigurations.

        Returns:
          Settings: The same settings instance if validation succeeds.

        Raises:
          ValueError: If `LOG_LEVEL` is not one of {"DEBUG","INFO","WARN","ERROR"}.
          ValueError: If `NEO4J_URI` does not start with "bolt://" or "neo4j://".
        """
        lvl = self.LOG_LEVEL.upper()
        if lvl not in {"DEBUG", "INFO", "WARN", "ERROR"}:
            raise ValueError(f"Invalid LOG_LEVEL: {self.LOG_LEVEL}")
        if not self.NEO4J_URI.startswith(("bolt://", "neo4j://")):
            raise ValueError("NEO4J_URI must start with bolt:// or neo4j://")
        return self


def load_settings() -> Settings:
    """Load settings from environment variables and validate them.

    Defaults are sensible for local `docker-compose` usage. This function avoids
    raising on missing optional LLM values so the demo can run without a real
    provider.

    Returns:
      Settings: A validated `Settings` instance loaded from the environment.
    """
    return Settings(
        LLM_MODEL=os.getenv("LLM_MODEL"),
        LLM_API_BASE=os.getenv("LLM_API_BASE"),
        LLM_API_KEY=os.getenv("LLM_API_KEY"),
        OTEL_ENDPOINT=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        SERVICE_NAME=os.getenv("SERVICE_NAME", "graph-rag-governor"),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        NEO4J_URI=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
        NEO4J_USER=os.getenv("NEO4J_USER", "neo4j"),
        NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD", "test"),
        MLFLOW_TRACKING_URI=os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
    ).validate()


# Singleton-like instance used across modules
settings = load_settings()
