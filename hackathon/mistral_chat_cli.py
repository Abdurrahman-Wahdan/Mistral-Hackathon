#!/usr/bin/env python3
import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request


DEFAULT_API_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_MODEL = "mistral-large-latest"
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def chat_completion(
    api_key: str,
    api_url: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    ssl_context = build_ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=ssl_context) as response:
            body = response.read().decode("utf-8")
            result = json.loads(body)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise RuntimeError(
                "HTTP 401 Unauthorized: MISTRAL_API_KEY is invalid/inactive for this endpoint."
            ) from exc
        raise RuntimeError(f"HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError(f"No choices returned. Raw response: {result}")
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        # Handle structured content formats if returned by the API.
        return " ".join(
            item.get("text", "") if isinstance(item, dict) else str(item) for item in content
        ).strip()
    return str(content).strip()


def build_ssl_context() -> ssl.SSLContext:
    # Prefer certifi bundle when available to avoid local trust-store issues.
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def run_test(api_key: str, api_url: str, model: str) -> int:
    prompt = "Reply with EXACT text: MISTRAL_CONNECTION_OK"
    reply = chat_completion(
        api_key=api_key,
        api_url=api_url,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    print(reply)
    if "MISTRAL_CONNECTION_OK" in reply:
        print("Connection test passed.")
        return 0
    print("Connection test got an unexpected response, but API call succeeded.")
    return 0


def run_chat(api_key: str, api_url: str, model: str, system_prompt: str | None) -> int:
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    print(f"Connected. Model: {model}")
    print("Type your message. Commands: /exit, /reset")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return 0

        if not user_input:
            continue
        if user_input.lower() in {"/exit", "exit", "quit"}:
            print("Exiting.")
            return 0
        if user_input.lower() == "/reset":
            messages = ([{"role": "system", "content": system_prompt}] if system_prompt else [])
            print("Conversation reset.")
            continue

        messages.append({"role": "user", "content": user_input})
        try:
            reply = chat_completion(api_key=api_key, api_url=api_url, model=model, messages=messages)
        except RuntimeError as exc:
            print(f"error> {exc}", file=sys.stderr)
            continue

        print(f"bot> {reply}")
        messages.append({"role": "assistant", "content": reply})


def main() -> int:
    parser = argparse.ArgumentParser(description="Simple Mistral CLI chat and connection test")
    parser.add_argument("--model", default=None, help="Mistral model name (overrides MISTRAL_MODEL)")
    parser.add_argument(
        "--api-url",
        default=None,
        help="Mistral chat completions endpoint (overrides MISTRAL_API_URL)",
    )
    parser.add_argument("--test", action="store_true", help="Run one-shot API connection test")
    parser.add_argument("--system", default=None, help="Optional system prompt")
    args = parser.parse_args()

    load_dotenv(".env")
    api_key = os.getenv("MISTRAL_API_KEY")
    api_url = args.api_url or os.getenv("MISTRAL_API_URL") or DEFAULT_API_URL
    model = args.model or os.getenv("MISTRAL_MODEL") or DEFAULT_MODEL

    if not api_key:
        print("Missing MISTRAL_API_KEY. Set it in environment or .env file.", file=sys.stderr)
        return 1
    if UUID_RE.fullmatch(api_key):
        print(
            "Warning: MISTRAL_API_KEY looks like a UUID; this is usually not a valid Mistral API token.",
            file=sys.stderr,
        )
        print(
            "Generate a real key from console.mistral.ai and replace MISTRAL_API_KEY in .env.",
            file=sys.stderr,
        )
    if not api_url:
        print("Missing MISTRAL_API_URL. Set it in environment or .env file.", file=sys.stderr)
        return 1
    if not model:
        print("Missing MISTRAL_MODEL. Set it in environment or .env file.", file=sys.stderr)
        return 1

    if args.test:
        return run_test(api_key=api_key, api_url=api_url, model=model)
    return run_chat(api_key=api_key, api_url=api_url, model=model, system_prompt=args.system)


if __name__ == "__main__":
    raise SystemExit(main())
