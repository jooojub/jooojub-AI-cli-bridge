FROM python:3.11-slim

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        bash \
        zstd \
        libsecret-1-0 \
        && rm -rf /var/lib/apt/lists/*

# ── gosu (privilege drop) ───────────────────────────────────────────────────────
RUN curl -fsSL -o /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/1.17/gosu-amd64" \
    && chmod +x /usr/local/bin/gosu

# ── Non-root app user ────────────────────────────────────────────────────────────
# claude's --dangerously-skip-permissions (used for interactive_mode=accept)
# refuses to run as root, so the server runs as this user instead.
# UID/GID are build args so they can match the host user — some mounted host
# files (e.g. ~/.claude/.credentials.json) are 0600 and unreadable by any
# other UID. entrypoint.sh does the root-only setup, then `gosu`s down to
# this user before starting uvicorn.
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupadd -g "${HOST_GID}" appuser \
    && useradd -m -u "${HOST_UID}" -g appuser -s /bin/bash appuser

# ── Node.js 20 LTS (for claude and gemini CLIs) ────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Claude CLI ─────────────────────────────────────────────────────────────────
RUN npm install -g @anthropic-ai/claude-code

# ── Antigravity CLI (agy) ──────────────────────────────────────────────────────
# Successor to the (now retired) Gemini CLI. The installer puts the `agy`
# binary under $HOME/.local/bin — at build time $HOME is /root, which
# appuser can't traverse into (/root is 0700) — so move the binary to
# /usr/local/bin where it's reachable by any user.
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash \
    && mv /root/.local/bin/agy /usr/local/bin/agy

# ── Ollama CLI ─────────────────────────────────────────────────────────────────
# Installs the `ollama` binary; we do NOT start the ollama server here —
# the server runs on the host and is reached via OLLAMA_HOST.
RUN curl -fsSL https://ollama.com/install.sh | OLLAMA_NO_AUTOSTART=1 sh

# ── Python app ─────────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
