FROM python:3.11-slim

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        bash \
        zstd \
        && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 LTS (for claude and gemini CLIs) ────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Claude CLI ─────────────────────────────────────────────────────────────────
RUN npm install -g @anthropic-ai/claude-code

# ── Gemini CLI ─────────────────────────────────────────────────────────────────
RUN npm install -g @google/gemini-cli

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
