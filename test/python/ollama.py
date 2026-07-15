#!/usr/bin/env python3
"""Test POST /v1/ollama/chat

Usage: python3 ollama.py ["prompt"] [model] [interactive_mode] [timeout]
  prompt            default: "What is the capital of France?"
  model             default: OLLAMA_DEFAULT_MODEL from .env, else llama3.2
  interactive_mode  accept | reject (default: reject)
  timeout           seconds (default: 30)
"""
import sys

from _common import get_config, post_chat, print_result


def main() -> int:
    args = sys.argv[1:] + [""] * 4
    prompt = args[0] or "What is the capital of France?"
    model = args[1] or get_config()["ollama_default_model"]
    interactive_mode = args[2] or "reject"
    timeout = int(args[3]) if args[3] else 30

    status, payload = post_chat(
        "/v1/ollama/chat",
        {"prompt": prompt, "model": model, "interactive_mode": interactive_mode, "timeout": timeout},
    )
    print_result(status, payload)
    return 0 if payload.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
