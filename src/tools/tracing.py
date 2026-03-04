"""
LangSmith tracing + LLM provider abstraction for FinAgent.

Provider selection via LLM_PROVIDER env var:
  LLM_PROVIDER=anthropic  (default) → direct Anthropic API
  LLM_PROVIDER=bedrock              → AWS Bedrock via AnthropicBedrock

Key exports:
  setup_langsmith()     → configure tracing from environment
  get_traced_client()   → return the correct (optionally traced) client
  resolve_model_id(name)→ map logical model name to provider-specific ID
  traceable             → re-export @traceable decorator

AWS Bedrock credentials are read from the standard AWS credential chain:
  1. Explicit env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
  2. ~/.aws/credentials profile (AWS_PROFILE)
  3. EC2/ECS/Lambda IAM role (when deployed on AWS)

Interview demo tip:
  Open https://smith.langchain.com → project "finagent-demo" to see the
  full agent reasoning tree with RAG retrieval steps and LLM calls.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ── Bedrock model ID mapping ─────────────────────────────────────────────────
# Maps logical names (used in agent code) to AWS Bedrock cross-region
# inference profile IDs.  Cross-region profiles (us.*) automatically
# route to the nearest available region for higher availability.
#
# Override any individual mapping via env vars:
#   BEDROCK_MODEL_SONNET=<custom-model-id>
#   BEDROCK_MODEL_HAIKU=<custom-model-id>
#   BEDROCK_MODEL_OPUS=<custom-model-id>

_BEDROCK_DEFAULTS: dict[str, str] = {
    # Claude 4 — verified cross-region inference profile IDs (us-east-1)
    "claude-sonnet-4-6": "us.anthropic.claude-sonnet-4-6",
    "claude-haiku-4-5-20251001": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "claude-opus-4-6": "us.anthropic.claude-opus-4-6-v1",
    # Claude 3.x — stable fallback IDs
    "claude-3-7-sonnet-20250219": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "claude-3-5-sonnet-20241022": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "claude-3-5-haiku-20241022": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "claude-3-opus-20240229": "us.anthropic.claude-3-opus-20240229-v1:0",
}


def resolve_model_id(logical_name: str) -> str:
    """
    Return the provider-specific model ID for a logical model name.

    For LLM_PROVIDER=anthropic: returns the logical name unchanged
      (Anthropic API accepts 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001', etc.)

    For LLM_PROVIDER=bedrock: maps to a Bedrock cross-region inference profile ID.
      Individual models can be overridden via BEDROCK_MODEL_SONNET / _HAIKU / _OPUS.

    Example:
        resolve_model_id("claude-sonnet-4-6")
        # anthropic → "claude-sonnet-4-6"
        # bedrock   → "us.anthropic.claude-sonnet-4-5-20251001-v1:0"
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

    if provider != "bedrock":
        return logical_name

    # Allow per-tier env overrides
    env_overrides = {
        "claude-sonnet-4-6": os.getenv("BEDROCK_MODEL_SONNET"),
        "claude-haiku-4-5-20251001": os.getenv("BEDROCK_MODEL_HAIKU"),
        "claude-opus-4-6": os.getenv("BEDROCK_MODEL_OPUS"),
    }
    if logical_name in env_overrides and env_overrides[logical_name]:
        return env_overrides[logical_name]

    mapped = _BEDROCK_DEFAULTS.get(logical_name)
    if not mapped:
        logger.warning(
            "No Bedrock model ID found for '%s'. "
            "Using as-is — set BEDROCK_MODEL_SONNET/HAIKU/OPUS to override.",
            logical_name,
        )
        return logical_name

    return mapped


# ── LangSmith setup ──────────────────────────────────────────────────────────

def setup_langsmith(project_name: Optional[str] = None) -> bool:
    """
    Configure LangSmith tracing from environment variables.

    Required for tracing:
        LANGCHAIN_API_KEY       — LangSmith API key
        LANGCHAIN_TRACING_V2   — "true" to enable

    Optional:
        LANGCHAIN_PROJECT       — project name in LangSmith UI (default: finagent)
        LANGCHAIN_ENDPOINT      — custom endpoint

    Returns True if tracing is enabled.
    """
    api_key = os.getenv("LANGCHAIN_API_KEY", "")
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

    if not api_key or not tracing_enabled:
        if not api_key:
            logger.info("LangSmith tracing disabled: LANGCHAIN_API_KEY not set.")
        else:
            logger.info("LangSmith tracing disabled: set LANGCHAIN_TRACING_V2=true.")
        return False

    if project_name:
        os.environ["LANGCHAIN_PROJECT"] = project_name
    elif not os.getenv("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = "finagent"

    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    logger.info(
        "LangSmith tracing enabled → project: %s, provider: %s",
        os.getenv("LANGCHAIN_PROJECT"),
        provider,
    )
    return True


# ── Client factory ───────────────────────────────────────────────────────────

def get_traced_client():
    """
    Return a (optionally LangSmith-traced) LLM client based on LLM_PROVIDER.

    LLM_PROVIDER=anthropic (default):
        Returns wrap_anthropic(Anthropic()) using ANTHROPIC_API_KEY.

    LLM_PROVIDER=bedrock:
        Returns wrap_anthropic(AnthropicBedrock(...)) using AWS credentials.
        AWS credentials are read from the standard chain:
          - AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (+ AWS_SESSION_TOKEN)
          - ~/.aws/credentials via AWS_PROFILE
          - IAM role (EC2/ECS/Lambda)

    The returned client has the same interface as Anthropic().messages.create()
    so all agent code works unchanged regardless of provider.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    tracing_on = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_key = os.getenv("LANGCHAIN_API_KEY", "")

    def _wrap(client):
        """Apply LangSmith wrapping when tracing is configured."""
        if not tracing_on or not langsmith_key:
            return client
        try:
            from langsmith.wrappers import wrap_anthropic
            return wrap_anthropic(client)
        except ImportError:
            logger.warning("langsmith not installed — tracing unavailable.")
            return client

    if provider == "bedrock":
        return _make_bedrock_client(_wrap)

    return _make_anthropic_client(_wrap)


def _make_anthropic_client(wrap_fn):
    """Build a direct Anthropic API client."""
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to .env or set LLM_PROVIDER=bedrock for AWS Bedrock."
        )
    return wrap_fn(Anthropic(api_key=api_key))


def _make_bedrock_client(wrap_fn):
    """
    Build an AWS Bedrock Anthropic client.

    Reads credentials from the standard AWS chain.
    Explicit env vars take priority over ~/.aws/credentials.
    """
    try:
        from anthropic import AnthropicBedrock
    except ImportError as exc:
        raise ImportError(
            "AnthropicBedrock requires 'anthropic[bedrock]'. "
            "Run: pip install 'anthropic[bedrock]'"
        ) from exc

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    session_token = os.getenv("AWS_SESSION_TOKEN")

    kwargs: dict = {"aws_region": region}
    if access_key and secret_key:
        kwargs["aws_access_key"] = access_key
        kwargs["aws_secret_key"] = secret_key
        if session_token:
            kwargs["aws_session_token"] = session_token
    # If no explicit keys, AnthropicBedrock falls back to boto3 credential chain
    # (IAM role, AWS_PROFILE, ~/.aws/credentials)

    logger.info("Using AWS Bedrock in region: %s", region)
    client = AnthropicBedrock(**kwargs)

    # Wrap client to provide clearer credential expiry messages
    original_create = client.messages.create

    def _create_with_cred_check(*args, **kw):
        try:
            return original_create(*args, **kw)
        except Exception as exc:
            msg = str(exc)
            if "security token" in msg.lower() and "expired" in msg.lower():
                token_hint = (
                    "AWS_SESSION_TOKEN (臨時憑證)" if session_token
                    else "AWS credentials (~/.aws/credentials 或 IAM role)"
                )
                raise RuntimeError(
                    f"AWS 憑證已過期：{token_hint} 已失效。\n"
                    f"請執行 'aws sso login' 或重新設定 AWS_ACCESS_KEY_ID / "
                    f"AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN。\n"
                    f"原始錯誤：{msg}"
                ) from exc
            raise

    client.messages.create = _create_with_cred_check  # type: ignore[method-assign]
    return wrap_fn(client)


# ── @traceable re-export ─────────────────────────────────────────────────────

try:
    from langsmith import traceable  # noqa: F401
except ImportError:
    def traceable(_func=None, *, name=None, run_type=None, metadata=None, tags=None):  # type: ignore[misc]
        """No-op @traceable when langsmith is not installed."""
        def decorator(func):
            return func
        return decorator(_func) if _func is not None else decorator


__all__ = [
    "setup_langsmith",
    "get_traced_client",
    "resolve_model_id",
    "traceable",
]
