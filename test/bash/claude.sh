#!/bin/bash
# Test POST /v1/claude/chat
#
# Usage: ./claude.sh ["prompt"] [interactive_mode] [timeout]
#   prompt            default: "What is 2+2? Answer in one short sentence."
#   interactive_mode  accept | reject (default: reject)
#   timeout           seconds (default: 30)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

PROMPT="${1:-What is 2+2? Answer in one short sentence.}"
MODE="${2:-reject}"
TIMEOUT="${3:-30}"

JSON_BODY="{\"prompt\": \"$(_json_escape "$PROMPT")\", \"interactive_mode\": \"$MODE\", \"timeout\": $TIMEOUT}"

_post_chat "/v1/claude/chat" "$JSON_BODY"
_print_result
_exit_on_success
