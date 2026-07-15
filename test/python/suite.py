#!/usr/bin/env python3
"""TC-style test suite: runs a fixed set of numbered test cases against a
live bridge instance and reports PASS/FAIL per case plus a summary. Exit
code is 0 only if every case passed -- safe to use as a CI/smoke-test gate.

Usage: python3 suite.py
Config: same as the other test/ scripts -- reads API_TOKEN/OLLAMA_DEFAULT_MODEL
        from ../../.env, overridable via API_TOKEN/BASE_URL env vars.
"""
import os
import sys
import time

from _common import get_json, post_chat

PASS = 0
FAIL = 0


def tc(tc_id: str, desc: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {tc_id}: {desc}")
    else:
        FAIL += 1
        suffix = f" -- {detail}" if detail else ""
        print(f"[FAIL] {tc_id}: {desc}{suffix}")


def main() -> int:
    # TC01: GET /health -> 200 + {"status":"ok"}
    status, payload = get_json("/health")
    tc("TC01", "GET /health returns 200 + status ok", status == 200 and payload.get("status") == "ok", f"HTTP {status} body={payload}")

    # TC02: valid token -> 200
    status, _ = post_chat("/v1/claude/chat", {"prompt": "hi"})
    tc("TC02", "valid token on /v1/claude/chat -> 200", status == 200, f"HTTP {status}")

    # TC03: invalid token -> 401
    status, _ = post_chat("/v1/claude/chat", {"prompt": "hi"}, token="wrong-token-xyz")
    tc("TC03", "invalid token on /v1/claude/chat -> 401", status == 401, f"HTTP {status}")

    # TC04: claude basic chat -> success:true
    status, payload = post_chat("/v1/claude/chat", {"prompt": "What is 2+2? Answer in one short sentence."})
    tc("TC04", "claude basic chat -> success:true", status == 200 and payload.get("success") is True, f"HTTP {status} body={payload}")

    # TC05: gemini/agy basic chat -> success:true
    status, payload = post_chat("/v1/gemini/chat", {"prompt": "What is 2+2? Answer in one short sentence."})
    tc("TC05", "gemini/agy basic chat -> success:true", status == 200 and payload.get("success") is True, f"HTTP {status} body={payload}")

    # TC06: claude skill listing -> success + at least 5 skills reported.
    # Loose on purpose: installed skills vary by machine, and the model
    # doesn't always list every single one deterministically.
    status, payload = post_chat(
        "/v1/claude/chat",
        {
            "prompt": "List every Skill name you have available via the Skill tool, one per line, nothing else.",
            "interactive_mode": "accept",
            "timeout": 60,
        },
    )
    line_count = len([l for l in str(payload.get("response", "")).splitlines() if l.strip()]) if status == 200 and payload.get("success") else 0
    tc("TC06", "claude skill listing -> success + >=5 skills reported", status == 200 and payload.get("success") is True and line_count >= 5, f"HTTP {status} lines={line_count}")

    # TC07/TC08: interactive_mode actually gates tool use (Write tool),
    # verified by asking claude to write a marker string to a file and read
    # it straight back in the same request -- no filesystem inspection needed.
    marker = f"TC_MARKER_{os.getpid()}_{int(time.time())}"
    write_prompt = (
        f"Use the Write tool to create /tmp/tc_probe_{os.getpid()}.txt containing exactly: "
        f"{marker} -- then use the Read tool to read that file back and print its exact contents."
    )

    # TC07: reject -> the write should be denied, so the marker must NOT appear
    status, payload = post_chat("/v1/claude/chat", {"prompt": write_prompt, "interactive_mode": "reject", "timeout": 30})
    contains_marker = marker in str(payload.get("response", ""))
    tc("TC07", "claude interactive_mode=reject blocks Write tool", status == 200 and not contains_marker, f"HTTP {status} body={payload}")

    # TC08: accept -> the write should succeed, so the marker must appear back
    status, payload = post_chat("/v1/claude/chat", {"prompt": write_prompt, "interactive_mode": "accept", "timeout": 30})
    contains_marker = marker in str(payload.get("response", ""))
    tc("TC08", "claude interactive_mode=accept allows Write tool", status == 200 and contains_marker, f"HTTP {status} body={payload}")

    # TC09: ollama endpoint returns well-formed JSON regardless of whether a
    # real ollama server is reachable on this host (that's an environment
    # concern, not something this bridge's own test suite should assert on).
    status, payload = post_chat("/v1/ollama/chat", {"prompt": "What is the capital of France?", "timeout": 15})
    tc("TC09", "ollama endpoint responds with well-formed JSON", status == 200 and "model" in payload, f"HTTP {status} body={payload}")

    # TC10: a short timeout bounds the request's wall-clock time (regression
    # guard against the bridge hanging indefinitely on a slow CLI response).
    start = time.monotonic()
    status, _ = post_chat("/v1/claude/chat", {"prompt": "Write a 5000 word essay about the history of computing.", "timeout": 3})
    elapsed = time.monotonic() - start
    tc("TC10", f"claude respects a short timeout (responded in {elapsed:.1f}s)", status == 200 and elapsed <= 25, f"HTTP {status} elapsed={elapsed:.1f}s")

    print()
    print("===================================================")
    print(f"Passed: {PASS}  Failed: {FAIL}  Total: {PASS + FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
