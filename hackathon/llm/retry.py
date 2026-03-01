import asyncio
import random
import re
import time
from typing import Any

import httpx

from hackathon.config.settings import settings


RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
RETRYABLE_PATTERNS = (
    "rate limit",
    "rate_limited",
    "too many requests",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "connection",
    "connecterror",
    "service unavailable",
)


def _extract_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    if response is not None:
        response_code = getattr(response, "status_code", None)
        if isinstance(response_code, int):
            return response_code

    message = str(exc)
    match = re.search(r"\b(408|409|425|429|500|502|503|504)\b", message)
    return int(match.group(1)) if match else None


def is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)):
        return True

    status_code = _extract_status_code(exc)
    if status_code in RETRYABLE_STATUS_CODES:
        return True

    message = str(exc).lower()
    return any(pattern in message for pattern in RETRYABLE_PATTERNS)


def _compute_delay(attempt: int) -> float:
    base = settings.LLM_RETRY_BASE_DELAY_SECONDS
    max_delay = settings.LLM_RETRY_MAX_DELAY_SECONDS
    jitter_ratio = settings.LLM_RETRY_JITTER_RATIO

    exponential = min(max_delay, base * (2 ** attempt))
    jitter = random.uniform(0, exponential * max(0.0, jitter_ratio))
    return exponential + jitter


def invoke_with_retry(runnable: Any, messages: list[Any], max_retries: int | None = None):
    retries = settings.LLM_MAX_RETRIES if max_retries is None else max_retries
    attempt = 0
    while True:
        try:
            return runnable.invoke(messages)
        except Exception as exc:
            if attempt >= retries or not is_retryable_exception(exc):
                raise
            time.sleep(_compute_delay(attempt))
            attempt += 1


async def ainvoke_with_retry(runnable: Any, messages: list[Any], max_retries: int | None = None):
    retries = settings.LLM_MAX_RETRIES if max_retries is None else max_retries
    attempt = 0
    while True:
        try:
            return await runnable.ainvoke(messages)
        except Exception as exc:
            if attempt >= retries or not is_retryable_exception(exc):
                raise
            await asyncio.sleep(_compute_delay(attempt))
            attempt += 1

