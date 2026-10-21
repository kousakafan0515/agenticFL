"""Dedicated OpenAI-compatible API adapter for the Stage3 server aggregator.

The aggregation model is intentionally isolated from the ALFWorld client
models.  This module reads only STAGE3_AGGREGATION_* variables and never logs,
serializes, or returns the API key.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from openai import OpenAI


BASE_URL_ENV = "STAGE3_AGGREGATION_BASE_URL"
API_KEY_ENV = "STAGE3_AGGREGATION_API_KEY"
MODEL_ENV = "STAGE3_AGGREGATION_MODEL"


class AggregationAPIConfigError(RuntimeError):
    """Raised before any network request when aggregation settings are unsafe."""


@dataclass(frozen=True)
class AggregationAPIConfig:
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AggregationAPIConfig":
        source = os.environ if environ is None else environ
        missing = [
            name
            for name in (BASE_URL_ENV, API_KEY_ENV, MODEL_ENV)
            if not source.get(name, "").strip()
        ]
        if missing:
            raise AggregationAPIConfigError(
                "Missing aggregation environment variables: " + ", ".join(missing)
            )

        raw_url = source[BASE_URL_ENV].strip().rstrip("/")
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise AggregationAPIConfigError(
                f"{BASE_URL_ENV} must be an absolute http(s) URL"
            )
        if parsed.username or parsed.password:
            raise AggregationAPIConfigError(
                f"{BASE_URL_ENV} must not contain credentials"
            )
        if parsed.query or parsed.fragment:
            raise AggregationAPIConfigError(
                f"{BASE_URL_ENV} must not contain a query string or fragment"
            )

        model = source[MODEL_ENV].strip()
        if any(char.isspace() for char in model):
            raise AggregationAPIConfigError(
                f"{MODEL_ENV} must be one exact model identifier without whitespace"
            )

        return cls(
            base_url=urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")),
            api_key=source[API_KEY_ENV].strip(),
            model=model,
        )

    def descriptor(self) -> dict[str, Any]:
        """Return non-secret metadata safe for logs and experiment manifests."""
        parsed = urlsplit(self.base_url)
        hostname = (parsed.hostname or "").lower()
        if hostname == "api.deepseek.com":
            provider = "deepseek_official"
        elif hostname == "api.openai.com":
            provider = "openai_official"
        else:
            provider = "openai_compatible_relay"
        return {
            "provider": provider,
            "endpoint_origin": f"{parsed.scheme}://{parsed.netloc}",
            "endpoint_path": parsed.path or "/",
            "model": self.model,
            "api_key_present": bool(self.api_key),
            "api_key_value_recorded": False,
        }

    def client(self, *, timeout: float = 60.0) -> OpenAI:
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=0,
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_live_probe(
    config: AggregationAPIConfig, *, timeout: float, max_tokens: int
) -> dict[str, Any]:
    """Send one deliberately tiny request that proves endpoint and model access."""
    started_at = utc_now()
    disable_thinking = config.model.lower().startswith("qwen")
    response = config.client(timeout=timeout).chat.completions.create(
        model=config.model,
        messages=[
            {
                "role": "system",
                "content": "This is an API connectivity check. Follow the user's exact output request.",
            },
            {"role": "user", "content": "Return exactly: OK"},
        ],
        temperature=0,
        max_tokens=max_tokens,
        stream=False,
        **({"extra_body": {"enable_thinking": False}} if disable_thinking else {}),
    )
    message = response.choices[0].message if response.choices else None
    content = message.content or "" if message is not None else ""
    reasoning = getattr(message, "reasoning_content", None) if message is not None else None
    if reasoning is None and message is not None:
        model_extra = getattr(message, "model_extra", None) or {}
        reasoning = model_extra.get("reasoning_content")
    reasoning = reasoning or ""
    usage = getattr(response, "usage", None)
    return {
        "status": "pass",
        "started_at": started_at,
        "finished_at": utc_now(),
        "request": {
            "model": config.model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
            "enable_thinking": False if disable_thinking else None,
        },
        "response": {
            "id_present": bool(getattr(response, "id", None)),
            "choice_count": len(response.choices),
            "content_is_ok": content.strip() == "OK",
            "content_character_count": len(content),
            "reasoning_content_present": bool(reasoning),
            "reasoning_character_count": len(reasoning),
            "finish_reason": (
                getattr(response.choices[0], "finish_reason", None) if response.choices else None
            ),
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            },
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate or probe the dedicated Stage3 aggregation API"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    probe = subparsers.add_parser("probe")
    probe.add_argument(
        "--live",
        action="store_true",
        help="Send one real chat completion capped at eight output tokens",
    )
    probe.add_argument("--timeout", type=float, default=60.0)
    probe.add_argument(
        "--max-tokens",
        type=int,
        default=128,
        help="Maximum output tokens for the live probe; reasoning models need room before text output",
    )
    probe.add_argument("--report", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = AggregationAPIConfig.from_env()
    report: dict[str, Any] = {
        "report_schema_version": "stage3.aggregation_api_probe.v1",
        "generated_at": utc_now(),
        "configuration": config.descriptor(),
        "live_request_performed": bool(args.live),
    }
    if args.live:
        if args.max_tokens < 1 or args.max_tokens > 512:
            raise SystemExit("--max-tokens must be between 1 and 512 for a connectivity probe")
        report["probe"] = run_live_probe(
            config, timeout=args.timeout, max_tokens=args.max_tokens
        )
    else:
        report["probe"] = {"status": "configuration_valid"}

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
