#!/bin/bash
set -e

# ── D-Bus machine-id ──────────────────────────────────────────────────────────
# libsecret/keychain requires a machine-id to initialise D-Bus.
# Docker containers don't have one by default, so generate a stable one.
if [ ! -s /etc/machine-id ]; then
    cat /proc/sys/kernel/random/uuid | tr -d '-' > /etc/machine-id
fi
if [ ! -f /var/lib/dbus/machine-id ]; then
    mkdir -p /var/lib/dbus
    cp /etc/machine-id /var/lib/dbus/machine-id
fi

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
