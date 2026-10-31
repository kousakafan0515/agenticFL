"""Frozen DeepSeek Teacher configuration shared by V12 evolvers."""

from __future__ import annotations

import os

from stage2_local_v12.federation.aggregation_api import AggregationAPIConfig


LOCAL_EVOLUTION_BASE_URL_ENV = "LOCAL_EVOLUTION_BASE_URL"
LOCAL_EVOLUTION_API_KEY_ENV = "LOCAL_EVOLUTION_API_KEY"
LOCAL_EVOLUTION_MODEL_ENV = "LOCAL_EVOLUTION_MODEL"
LOCAL_EVOLUTION_MODEL = "deepseek-v4.1-flash"


def _local_evolution_config(environ: dict[str, str] | None = None) -> AggregationAPIConfig:
    """Preserve the V10 environment projection without importing legacy modules."""
    source = os.environ if environ is None else environ
    projected = {
        "STAGE3_AGGREGATION_BASE_URL": source.get(
            LOCAL_EVOLUTION_BASE_URL_ENV,
            source.get("STAGE3_AGGREGATION_BASE_URL", ""),
        ),
        "STAGE3_AGGREGATION_API_KEY": source.get(
            LOCAL_EVOLUTION_API_KEY_ENV,
            source.get("STAGE3_AGGREGATION_API_KEY", ""),
        ),
        "STAGE3_AGGREGATION_MODEL": source.get(
            LOCAL_EVOLUTION_MODEL_ENV,
            LOCAL_EVOLUTION_MODEL,
        ),
    }
    return AggregationAPIConfig.from_env(projected)
