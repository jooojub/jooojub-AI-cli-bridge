#!/usr/bin/env python3
"""Test POST /v1/claude/chat

Usage: python3 claude.py ["prompt"] [interactive_mode] [timeout]
  prompt            default: "What is 2+2? Answer in one short sentence."
  interactive_mode  accept | reject (default: reject)
  timeout           seconds (default: 30)
"""
import sys

from _common import post_chat, print_result


def main() -> int:
    args = sys.argv[1:] + [""] * 3
    prompt = args[0] or "What is 2+2? Answer in one short sentence."
    interactive_mode = args[1] or "reject"
    timeout = int(args[2]) if args[2] else 30

    status, payload = post_chat(
        "/v1/claude/chat",
        {"prompt": prompt, "interactive_mode": interactive_mode, "timeout": timeout},
    )
    print_result(status, payload)
    return 0 if payload.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
