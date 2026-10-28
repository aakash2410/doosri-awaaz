"""Thin wrapper around the Anthropic SDK used by the Prepare and Review stages.

The classroom loop never imports this module: it makes no network calls.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Type, TypeVar

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"
# Re-runs a request on Anthropic's recommended model if a safety classifier declines it.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ClaudeError(RuntimeError):
    """Raised when Claude cannot return a usable structured answer."""


_client: anthropic.Anthropic | None = None
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = None
        if ENV_FILE.exists():  # a local .env (gitignored) wins over the shell, so the hackathon key is used
            for line in ENV_FILE.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"')
        _client = anthropic.Anthropic(api_key=key, max_retries=3) if key else anthropic.Anthropic(max_retries=3)
    return _client


def structured(
    *, system: str, prompt: str, schema: Type[T], effort: str = "high", max_tokens: int = 32000
) -> T:
    """One Claude call whose output is validated against a Pydantic model."""
    try:
        response = client().beta.messages.parse(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        raise ClaudeError("Claude rate limit reached; try again in a minute") from e
    except anthropic.APIStatusError as e:
        raise ClaudeError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ClaudeError("Could not reach the Claude API; Prepare and Review need internet") from e

    log.info(
        "claude %s in=%s out=%s stop=%s",
        schema.__name__,
        response.usage.input_tokens,
        response.usage.output_tokens,
        response.stop_reason,
    )
    if response.stop_reason == "refusal":
        raise ClaudeError("Claude declined this request")
    if response.stop_reason == "max_tokens":
        raise ClaudeError("Claude's answer was cut off; shorten the source lesson")
    if response.parsed_output is None:
        raise ClaudeError("Claude returned output that did not match the schema")
    return response.parsed_output
