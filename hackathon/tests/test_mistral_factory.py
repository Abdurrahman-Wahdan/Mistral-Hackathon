#!/usr/bin/env python3
"""
Mistral factory smoke test:
1) Model discovery/parsing via list_mistral_models/list_all_models
2) Standard invoke response via get_llm
3) Streaming response and end metadata
"""

from __future__ import annotations

import argparse
import sys
from typing import Any
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage, SystemMessage

from llm.factory import get_llm, list_all_models, list_mistral_models


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return " ".join(parts).strip()
    return str(content).strip()


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def run(model_override: str | None = None) -> int:
    print("Step 1/3: Fetching and validating Mistral models...")
    models = list_mistral_models(force_refresh=True)
    if not models:
        return _fail("No models returned by list_mistral_models(). Check MISTRAL_API_KEY.")

    invalid = [m.get("id") for m in models if m.get("provider") != "mistral" or not m.get("id")]
    if invalid:
        return _fail(f"Invalid parsed model entries: {invalid[:3]}")

    print(f"OK: Parsed {len(models)} Mistral models")

    all_models = list_all_models(force_refresh=True)
    if "mistral" not in all_models:
        return _fail("list_all_models() missing 'mistral' key")
    print(f"OK: list_all_models() providers: {list(all_models.keys())}")

    available_ids = {m["id"] for m in models}
    model_id = model_override or models[0]["id"]
    if model_id not in available_ids:
        print(f"WARN: Requested model '{model_id}' not in fetched list. Falling back to '{models[0]['id']}'")
        model_id = models[0]["id"]
    print(f"Using model: {model_id}")

    messages = [
        SystemMessage(content="You are a concise test assistant."),
        HumanMessage(content="Reply exactly with: MISTRAL_FACTORY_OK"),
    ]

    print("Step 2/3: Testing invoke() response...")
    llm = get_llm(model_id=model_id, temperature=0.0, max_tokens=64)
    response = llm.invoke(messages)

    text = _extract_text(getattr(response, "content", ""))
    if not text:
        return _fail("invoke() returned empty content")

    response_meta = getattr(response, "response_metadata", {}) or {}
    finish_reason = (
        response_meta.get("finish_reason")
        or response_meta.get("stop_reason")
        or response_meta.get("finishReason")
    )

    print(f"OK: invoke() response: {text}")
    print(f"invoke() finish metadata: {finish_reason if finish_reason is not None else 'N/A'}")

    print("Step 3/3: Testing stream() and end metadata...")
    chunks = list(llm.stream(messages))
    if not chunks:
        return _fail("stream() returned no chunks")

    stream_text = "".join(_extract_text(getattr(chunk, "content", "")) for chunk in chunks).strip()
    if not stream_text:
        return _fail("stream() chunks produced empty combined content")

    stream_finish_reason = None
    for chunk in reversed(chunks):
        chunk_meta = getattr(chunk, "response_metadata", {}) or {}
        stream_finish_reason = (
            chunk_meta.get("finish_reason")
            or chunk_meta.get("stop_reason")
            or chunk_meta.get("finishReason")
        )
        if stream_finish_reason is not None:
            break

    print(f"OK: stream() response: {stream_text}")
    print(
        "stream() finish metadata: "
        f"{stream_finish_reason if stream_finish_reason is not None else 'N/A'}"
    )

    print("SUCCESS: Mistral model parsing and response flow are working.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for Mistral-only llm.factory")
    parser.add_argument("--model", default=None, help="Optional explicit model id to test")
    args = parser.parse_args()
    return run(model_override=args.model)


if __name__ == "__main__":
    raise SystemExit(main())
