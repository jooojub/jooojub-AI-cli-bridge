#!/bin/bash
set -e

# ── Gemini auth ────────────────────────────────────────────────────────────────
# The Gemini CLI writes runtime files (projects.json, checkpoints, etc.) to
# ~/.gemini, so the directory must be writable.  We mount the host credentials
# read-only at /mnt/gemini-auth and copy them into a writable ~/.gemini here.
if [ -d /mnt/gemini-auth ] && [ "$(ls -A /mnt/gemini-auth 2>/dev/null)" ]; then
    mkdir -p /root/.gemini
    cp -r /mnt/gemini-auth/. /root/.gemini/
fi

# ── Claude auth ────────────────────────────────────────────────────────────────
# Similarly, copy ~/.claude.json if mounted as read-only source.
if [ -f /mnt/claude-config/claude.json ]; then
    cp /mnt/claude-config/claude.json /root/.claude.json
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
