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

# ── Gemini / Antigravity (agy) auth ─────────────────────────────────────────────
# agy (the Antigravity CLI, successor to Gemini CLI) reuses the same ~/.gemini
# config dir and writes runtime files there, so it must be writable.  We mount
# the host credentials read-only at /mnt/gemini-auth and copy them into a
# writable ~/.gemini here.
if [ -d /mnt/gemini-auth ] && [ "$(ls -A /mnt/gemini-auth 2>/dev/null)" ]; then
    mkdir -p "$HOME/.gemini"
    cp -r /mnt/gemini-auth/. "$HOME/.gemini/"
    chown -R appuser:appuser "$HOME/.gemini"
fi

# ── Claude auth ────────────────────────────────────────────────────────────────
# Similarly, copy ~/.claude.json if mounted as read-only source.
if [ -f /mnt/claude-config/claude.json ]; then
    cp /mnt/claude-config/claude.json "$HOME/.claude.json"
    chown appuser:appuser "$HOME/.claude.json"
fi

# ── Claude Code runtime scratch dir ──────────────────────────────────────────
# $HOME/.claude/session-env is tmpfs-mounted (see docker-compose.yml) so the
# Bash tool can write its per-session bookkeeping there even though the rest
# of ~/.claude is read-only. tmpfs mounts default to root:root, so hand it
# to appuser (the user the server actually runs as, see below).
if [ -d "$HOME/.claude/session-env" ]; then
    chown appuser:appuser "$HOME/.claude/session-env"
fi

# ── Drop privileges ──────────────────────────────────────────────────────────
# claude's --dangerously-skip-permissions (used for interactive_mode=accept,
# see app/routes/claude.py) refuses to run as root, so the server itself —
# and every claude/agy/ollama subprocess it spawns — runs as appuser instead.
# appuser's UID/GID were set at build time to match the host user (Dockerfile
# ARGs HOST_UID/HOST_GID), so it can still read host-owned files that are
# mounted read-only, including 0600 ones like ~/.claude/.credentials.json.
#
# gosu resets HOME to appuser's own /etc/passwd entry (/home/appuser) when it
# drops privileges, undoing the HOME=${HOME} set in docker-compose.yml — so
# re-assert it explicitly for the process gosu execs, or claude/agy look for
# their config in the wrong (empty) home directory and report "Not logged in".
exec gosu appuser env HOME="$HOME" uvicorn app.main:app --host 0.0.0.0 --port 8000
