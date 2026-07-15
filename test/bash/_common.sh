#!/bin/bash
# Shared helpers for the bash test scripts. Not meant to be run directly —
# each endpoint script does `source "$SCRIPT_DIR/_common.sh"`.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    ENV_API_TOKEN=$(grep -E '^API_TOKEN=' "$ENV_FILE" | tail -1 | cut -d '=' -f2-)
    ENV_OLLAMA_DEFAULT_MODEL=$(grep -E '^OLLAMA_DEFAULT_MODEL=' "$ENV_FILE" | tail -1 | cut -d '=' -f2-)
fi

API_TOKEN="${API_TOKEN:-${ENV_API_TOKEN:-your-secret-token-here}}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
OLLAMA_DEFAULT_MODEL="${OLLAMA_DEFAULT_MODEL:-${ENV_OLLAMA_DEFAULT_MODEL:-llama3.2}}"

# Escapes a string for embedding inside a JSON string literal.
_json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s"
}

# _get ENDPOINT — unauthenticated GET, e.g. /health
_get() {
    local endpoint="$1"
    local response
    response=$(curl -s -w '\n%{http_code}' "$BASE_URL$endpoint")
    HTTP_CODE=$(echo "$response" | tail -1)
    BODY=$(echo "$response" | sed '$d')
}

# _post_chat ENDPOINT JSON_BODY
_post_chat() {
    local endpoint="$1"
    local json_body="$2"

    local response
    response=$(curl -s -w '\n%{http_code}' -X POST "$BASE_URL$endpoint" \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$json_body")

    HTTP_CODE=$(echo "$response" | tail -1)
    BODY=$(echo "$response" | sed '$d')
}

# _post_chat_as ENDPOINT JSON_BODY TOKEN — like _post_chat but with a
# caller-supplied bearer token, for auth-failure test cases.
_post_chat_as() {
    local endpoint="$1"
    local json_body="$2"
    local token="$3"

    local response
    response=$(curl -s -w '\n%{http_code}' -X POST "$BASE_URL$endpoint" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -d "$json_body")

    HTTP_CODE=$(echo "$response" | tail -1)
    BODY=$(echo "$response" | sed '$d')
}

_print_result() {
    echo "HTTP $HTTP_CODE"
    if command -v jq >/dev/null 2>&1; then
        echo "$BODY" | jq .
    else
        echo "$BODY"
    fi
}

# Exits 0 if the response body has "success": true, 1 otherwise.
_exit_on_success() {
    if command -v jq >/dev/null 2>&1; then
        [ "$(echo "$BODY" | jq -r '.success')" = "true" ]
    else
        echo "$BODY" | grep -q '"success"[[:space:]]*:[[:space:]]*true'
    fi
}
