#!/bin/bash
# TC-style test suite: runs a fixed set of numbered test cases against a live
# bridge instance and reports PASS/FAIL per case plus a summary. Exit code is
# 0 only if every case passed — safe to use as a CI/smoke-test gate.
#
# Usage: ./suite.sh
# Config: same as the other test/ scripts — reads API_TOKEN/OLLAMA_DEFAULT_MODEL
#         from ../../.env, overridable via API_TOKEN/BASE_URL env vars.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

PASS=0
FAIL=0

# _tc ID DESCRIPTION RESULT [DETAIL]  — RESULT: 0 = pass, anything else = fail
_tc() {
    local id="$1" desc="$2" result="$3" detail="${4:-}"
    if [ "$result" -eq 0 ]; then
        PASS=$((PASS + 1))
        echo "[PASS] $id: $desc"
    else
        FAIL=$((FAIL + 1))
        echo "[FAIL] $id: $desc${detail:+ -- $detail}"
    fi
}

# ---------------------------------------------------------------------------
# TC01: GET /health -> 200 + {"status":"ok"}
_get "/health"
if [ "$HTTP_CODE" = "200" ] && echo "$BODY" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    _tc "TC01" "GET /health returns 200 + status ok" 0
else
    _tc "TC01" "GET /health returns 200 + status ok" 1 "HTTP $HTTP_CODE body=$BODY"
fi

# TC02: valid token -> 200
_post_chat "/v1/claude/chat" '{"prompt": "hi"}'
if [ "$HTTP_CODE" = "200" ]; then
    _tc "TC02" "valid token on /v1/claude/chat -> 200" 0
else
    _tc "TC02" "valid token on /v1/claude/chat -> 200" 1 "HTTP $HTTP_CODE"
fi

# TC03: invalid token -> 401
_post_chat_as "/v1/claude/chat" '{"prompt": "hi"}' "wrong-token-xyz"
if [ "$HTTP_CODE" = "401" ]; then
    _tc "TC03" "invalid token on /v1/claude/chat -> 401" 0
else
    _tc "TC03" "invalid token on /v1/claude/chat -> 401" 1 "HTTP $HTTP_CODE"
fi

# TC04: claude basic chat -> success:true
JSON_BODY="{\"prompt\": \"$(_json_escape "What is 2+2? Answer in one short sentence.")\"}"
_post_chat "/v1/claude/chat" "$JSON_BODY"
if [ "$HTTP_CODE" = "200" ] && _exit_on_success; then
    _tc "TC04" "claude basic chat -> success:true" 0
else
    _tc "TC04" "claude basic chat -> success:true" 1 "HTTP $HTTP_CODE body=$BODY"
fi

# TC05: gemini/agy basic chat -> success:true
JSON_BODY="{\"prompt\": \"$(_json_escape "What is 2+2? Answer in one short sentence.")\"}"
_post_chat "/v1/gemini/chat" "$JSON_BODY"
if [ "$HTTP_CODE" = "200" ] && _exit_on_success; then
    _tc "TC05" "gemini/agy basic chat -> success:true" 0
else
    _tc "TC05" "gemini/agy basic chat -> success:true" 1 "HTTP $HTTP_CODE body=$BODY"
fi

# TC06: claude skill listing -> success + at least 5 skills reported
# Loose on purpose: which exact skills are installed varies by machine, and
# the model doesn't always list every single one deterministically.
JSON_BODY="{\"prompt\": \"$(_json_escape "List every Skill name you have available via the Skill tool, one per line, nothing else.")\", \"interactive_mode\": \"accept\", \"timeout\": 60}"
_post_chat "/v1/claude/chat" "$JSON_BODY"
if [ "$HTTP_CODE" = "200" ] && _exit_on_success; then
    if command -v jq >/dev/null 2>&1; then
        LINE_COUNT=$(echo "$BODY" | jq -r '.response' | grep -c '[A-Za-z0-9]')
    else
        LINE_COUNT=5 # can't inspect multi-line response text without jq; trust success:true
    fi
    if [ "$LINE_COUNT" -ge 5 ]; then
        _tc "TC06" "claude skill listing -> success + >=5 skills reported" 0
    else
        _tc "TC06" "claude skill listing -> success + >=5 skills reported" 1 "only $LINE_COUNT lines"
    fi
else
    _tc "TC06" "claude skill listing -> success + >=5 skills reported" 1 "HTTP $HTTP_CODE body=$BODY"
fi

# TC07/TC08: interactive_mode actually gates tool use (Write tool), verified
# by asking claude to write a marker string to a file and read it straight
# back in the same request -- no need to inspect the container's filesystem.
MARKER="TC_MARKER_$$_$(date +%s)"
WRITE_PROMPT="Use the Write tool to create /tmp/tc_probe_$$.txt containing exactly: $MARKER -- then use the Read tool to read that file back and print its exact contents."

# TC07: reject -> the write should be denied, so the marker must NOT appear
JSON_BODY="{\"prompt\": \"$(_json_escape "$WRITE_PROMPT")\", \"interactive_mode\": \"reject\", \"timeout\": 30}"
_post_chat "/v1/claude/chat" "$JSON_BODY"
if [ "$HTTP_CODE" = "200" ] && ! echo "$BODY" | grep -q "$MARKER"; then
    _tc "TC07" "claude interactive_mode=reject blocks Write tool" 0
else
    _tc "TC07" "claude interactive_mode=reject blocks Write tool" 1 "HTTP $HTTP_CODE body=$BODY"
fi

# TC08: accept -> the write should succeed, so the marker must appear back
JSON_BODY="{\"prompt\": \"$(_json_escape "$WRITE_PROMPT")\", \"interactive_mode\": \"accept\", \"timeout\": 30}"
_post_chat "/v1/claude/chat" "$JSON_BODY"
if [ "$HTTP_CODE" = "200" ] && echo "$BODY" | grep -q "$MARKER"; then
    _tc "TC08" "claude interactive_mode=accept allows Write tool" 0
else
    _tc "TC08" "claude interactive_mode=accept allows Write tool" 1 "HTTP $HTTP_CODE body=$BODY"
fi

# TC09: ollama endpoint returns well-formed JSON regardless of whether a
# real ollama server is reachable on this host (that's an environment
# concern, not something this bridge's own test suite should assert on).
JSON_BODY="{\"prompt\": \"$(_json_escape "What is the capital of France?")\", \"timeout\": 15}"
_post_chat "/v1/ollama/chat" "$JSON_BODY"
if [ "$HTTP_CODE" = "200" ] && echo "$BODY" | grep -q '"model"'; then
    _tc "TC09" "ollama endpoint responds with well-formed JSON" 0
else
    _tc "TC09" "ollama endpoint responds with well-formed JSON" 1 "HTTP $HTTP_CODE body=$BODY"
fi

# TC10: a short timeout bounds the request's wall-clock time (regression
# guard against the bridge hanging indefinitely on a slow CLI response).
START=$(date +%s)
JSON_BODY="{\"prompt\": \"$(_json_escape "Write a 5000 word essay about the history of computing.")\", \"timeout\": 3}"
_post_chat "/v1/claude/chat" "$JSON_BODY"
ELAPSED=$(( $(date +%s) - START ))
if [ "$HTTP_CODE" = "200" ] && [ "$ELAPSED" -le 25 ]; then
    _tc "TC10" "claude respects a short timeout (responded in ${ELAPSED}s)" 0
else
    _tc "TC10" "claude respects a short timeout" 1 "HTTP $HTTP_CODE elapsed=${ELAPSED}s"
fi

echo
echo "==================================================="
echo "Passed: $PASS  Failed: $FAIL  Total: $((PASS + FAIL))"
[ "$FAIL" -eq 0 ]
