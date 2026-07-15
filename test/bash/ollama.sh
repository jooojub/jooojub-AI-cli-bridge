#!/bin/bash
# Test POST /v1/ollama/chat
#
# Usage: ./ollama.sh ["prompt"] [model] [interactive_mode] [timeout]
#   prompt            default: "What is the capital of France?"
#   model             default: OLLAMA_DEFAULT_MODEL from .env, else llama3.2
#   interactive_mode  accept | reject (default: reject)
#   timeout           seconds (default: 30)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

PROMPT="${1:-What is the capital of France?}"
MODEL="${2:-$OLLAMA_DEFAULT_MODEL}"
MODE="${3:-reject}"
TIMEOUT="${4:-30}"

JSON_BODY="{\"prompt\": \"$(_json_escape "$PROMPT")\", \"model\": \"$(_json_escape "$MODEL")\", \"interactive_mode\": \"$MODE\", \"timeout\": $TIMEOUT}"

_post_chat "/v1/ollama/chat" "$JSON_BODY"
_print_result
_exit_on_success
