# AI CLI Bridge

RESTful API server that proxies requests to **claude**, **agy** (Antigravity CLI, the Gemini CLI successor — still exposed as `/v1/gemini/chat` for backwards compatibility), and **ollama** CLIs running inside a Docker container.

- Bearer token authentication via `.env`
- Two interactive modes: auto-accept or auto-reject CLI confirmation prompts
- OAuth credentials mounted read-only from the host

---

## System Architecture

The container never logs in on its own — it borrows whatever's already authenticated on the **host**, mounted in read-only, and just executes the CLI headlessly for each API request:

```
┌───────────────────────────── Host machine ──────────────────────────────┐
│                             (e.g. $HOME=/home/alice)                    │
│  ~/.claude.json, ~/.claude/       ~/.gemini/            ollama serve     │
│  (claude auth, sessions,          (agy/Antigravity CLI  (listens on      │
│   settings, skills, plugins)       auth, config, its     127.0.0.1       │
│                                     own skills)           :11434)        │
│  ~/.agents/skills/                                                       │
│  (some ~/.claude/skills/* entries are symlinks that point here)         │
│                                                                           │
│  Already authenticated once via `claude login` / agy sign-in /          │
│  `ollama pull <model>` on the host — the container reuses this as-is.   │
└──────────────┬───────────────────────────────┬──────────────────────────┘
               │ read-only bind mounts          │ plain HTTP (OLLAMA_HOST)
               ▼                                 ▼
┌───────────────────────── Docker container ──────────────────────────────┐
│              (HOME env var set to the same $HOME as the host)           │
│                                                                           │
│  entrypoint.sh (runs as root — this part only)                          │
│    - generates /etc/machine-id (needed by libsecret/D-Bus)              │
│    - copies ~/.claude.json  -> $HOME/.claude.json,  chown appuser        │
│    - copies ~/.gemini (ro)  -> $HOME/.gemini (writable — agy needs to    │
│      write projects.json/checkpoints back into its own config dir)      │
│    - $HOME/.claude, $HOME/.agents stay mounted read-only, no copy needed │
│    - chowns the tmpfs-mounted $HOME/.claude/session-env to appuser       │
│    - `exec gosu appuser env HOME="$HOME" uvicorn ...` — drops root       │
│                                                                           │
│  FastAPI (uvicorn, :8000, running as appuser from here on)               │
│    1. auth.py checks the `Authorization: Bearer` header                  │
│    2. cli_runner.py spawns `claude -p "..."` / `agy -p "..."` /          │
│       `ollama run <model>` in a pseudo-TTY (pexpect); claude.py adds     │
│       `--dangerously-skip-permissions` when interactive_mode=accept      │
│    3. ANSI/control characters are stripped from the raw CLI output       │
│                                                                           │
└──────────────┬────────────────────────────────────────────────────────────┘
               │ JSON response: {"llm", "response", "exit_code", "success"}
               ▼
     Caller (curl / the test/ scripts / your app) — Bearer <API_TOKEN>
```

A few things this diagram makes explicit:

- **Nothing is re-authenticated inside Docker.** All three backends reuse credentials/config that already exist on the host; mounts are `:ro` and the container never writes back to the host filesystem.
- **The container's `$HOME` is set to match the host's `$HOME`** (`environment: HOME=${HOME}` in `docker-compose.yml`), and `~/.claude` / `~/.agents` are mounted at that identical absolute path rather than remapped to `/root`. This matters because Claude Code's plugin/marketplace metadata (`~/.claude/plugins/known_marketplaces.json`, `installed_plugins.json`) stores **absolute host paths** — if the container's home directory doesn't line up with the host's, every marketplace-installed plugin (and the skills it provides) fails to load with a `cache-miss` error. This is portable across machines: `${HOME}` is resolved from whatever host actually runs `docker compose up`, so it's always self-consistent, not hardcoded to one person's path.
- **The server runs as a non-root user (`appuser`), not root.** `claude`'s `--dangerously-skip-permissions` (how `interactive_mode: accept` is implemented — see below) refuses to run as root, so `entrypoint.sh` does its root-only setup (D-Bus machine-id, copying/chowning the writable auth dirs) and then drops privileges via `gosu` before starting uvicorn. `appuser`'s UID/GID are baked in at build time (`HOST_UID`/`HOST_GID` build args, default `1000`) to match the host user — otherwise it couldn't read host-owned files that are `0600`, like `~/.claude/.credentials.json`. One gotcha we hit: `gosu` resets `HOME` to `appuser`'s own passwd entry when it drops privileges, silently undoing the `HOME=${HOME}` override — `entrypoint.sh` re-asserts it explicitly (`gosu appuser env HOME="$HOME" ...`) to work around that.
- **`~/.claude` and `~/.agents` are mounted straight through** (no copy step) because Claude Code only needs read access to run non-interactively. `~/.agents` matters specifically because some entries under `~/.claude/skills/` (e.g. `hud`, `stitch-design`) are symlinks pointing to `~/.agents/skills/...` — if only `~/.claude` were mounted, those skills would resolve to broken links inside the container.
- **`~/.gemini` is copied, not mounted directly**, because agy (the Antigravity CLI) writes runtime state (`projects.json`, checkpoints, etc.) back into the same directory it reads config from — a read-only mount would make the CLI fail on first write.
- **Ollama is different from the other two**: the container doesn't run an ollama *server*, only the `ollama` CLI binary, which talks over plain HTTP to a real ollama server running on the host (`OLLAMA_HOST` in `.env`). There's no auth to mount here, just network reachability from container to host.

---

## Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI app, route registration, GET /health
│   ├── auth.py               # Bearer token verification
│   ├── cli_runner.py          # pexpect-based CLI runner: spawns the CLI in a
│   │                          # pty, strips ANSI/control chars, auto-answers
│   │                          # y/n confirmation prompts per interactive_mode
│   └── routes/
│       ├── claude.py          # POST /v1/claude/chat  -> `claude -p "<prompt>"`
│       ├── gemini.py          # POST /v1/gemini/chat  -> `agy -p "<prompt>"`
│       └── ollama.py          # POST /v1/ollama/chat  -> `ollama run <model>`
│                              # (prompt piped via stdin, no shell involved)
├── test/                     # Standalone test scripts — one implementation
│   ├── bash/                  # per language, one file per endpoint
│   ├── node/
│   └── python/
├── Dockerfile                 # Installs Node/claude CLI, agy, ollama CLI
├── docker-compose.yml         # Builds the image, mounts host CLI auth dirs
├── entrypoint.sh              # Copies read-only auth mounts into writable
│                              # locations before starting uvicorn
├── .env.example
└── requirements.txt
```

---

## Requirements

- Docker & Docker Compose
- Host machine with **claude**, **agy** (Antigravity CLI), and/or **ollama** already authenticated
- (Ollama) ollama server running on the host
- Your host user's UID/GID — run `id -u` and `id -g`. If they're not `1000`/`1000` (the default), set `HOST_UID`/`HOST_GID` in `.env` — see [System Architecture](#system-architecture) for why the container needs to match.

---

## Quick Start

### 1. Generate an API Token

Pick one of the following:

```bash
# openssl (recommended)
openssl rand -hex 32

# /dev/urandom
head -c 32 /dev/urandom | base64 | tr -d '=+/' | head -c 32

# Python
python3 -c "import secrets; print(secrets.token_hex(32))"

# uuidgen (simple, less entropy)
uuidgen
```

Copy the output — you'll use it as `API_TOKEN`.

---

### 2. Create `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# Paste the token you generated above
API_TOKEN=a3f8c2d1e9b047...

# Ollama server on the host (Linux Docker default)
OLLAMA_HOST=http://172.17.0.1:11434

# Default model when none is specified in the request
OLLAMA_DEFAULT_MODEL=llama3.2

# Per-request CLI timeout in seconds
CLI_TIMEOUT=120
```

> **Never commit `.env` to git.** It is already in `.gitignore`.

---

### 3. Build & Run

```bash
docker compose up --build -d
```

Check logs:

```bash
docker compose logs -f
```

Health check:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### 4. Manual `docker run` (without Compose)

```bash
docker build -t ai-cli-bridge .

docker run -d \
  --name ai-cli-bridge \
  -p 8000:8000 \
  --env-file .env \
  -e HOME="$HOME" \
  --add-host host.docker.internal:host-gateway \
  -v "$HOME/.claude.json:/mnt/claude-config/claude.json:ro" \
  -v "$HOME/.claude:$HOME/.claude:ro" \
  -v "$HOME/.agents:$HOME/.agents:ro" \
  -v "$HOME/.gemini:/mnt/gemini-auth:ro" \
  ai-cli-bridge
```

---

## API Reference

All endpoints require:

```
Authorization: Bearer <API_TOKEN>
Content-Type: application/json
```

---

### POST `/v1/claude/chat`

```json
{
  "prompt": "Explain recursion in one sentence.",
  "interactive_mode": "accept",
  "timeout": 120
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | required | The prompt to send |
| `interactive_mode` | `"accept"` \| `"reject"` | `"reject"` | How to handle CLI confirmation prompts |
| `timeout` | int | `120` | Max seconds to wait for response |

---

### POST `/v1/gemini/chat`

Runs `agy` (Antigravity CLI) under the hood — the route/field names are kept as `gemini` for backwards compatibility. Same fields as `/v1/claude/chat`.

---

### POST `/v1/ollama/chat`

```json
{
  "prompt": "What is the capital of France?",
  "model": "llama3.2",
  "interactive_mode": "reject",
  "timeout": 120
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | required | The prompt to send |
| `model` | string | `OLLAMA_DEFAULT_MODEL` | Ollama model name |
| `interactive_mode` | `"accept"` \| `"reject"` | `"reject"` | How to handle CLI confirmation prompts |
| `timeout` | int | `120` | Max seconds to wait for response |

---

### Response

```json
{
  "llm": "claude",
  "response": "Recursion is a function calling itself.",
  "exit_code": 0,
  "success": true
}
```

`ollama` responses also include `"model": "llama3.2"`.

---

## Interactive Mode

Some CLI tools ask for confirmation when performing actions (e.g., tool use, file access, code execution).

| Mode | `/v1/claude/chat` behaviour | `/v1/gemini/chat`, `/v1/ollama/chat` behaviour |
|---|---|---|
| `"accept"` | Runs with `claude -p --dangerously-skip-permissions`, so permission-gated tool calls (Write, Bash outside the allowlist, WebFetch, etc.) actually execute | `cli_runner.py`'s pexpect loop answers `y` to any `[y/N]` / `Allow?` / `proceed?` prompt it sees on the pty |
| `"reject"` | Default `claude -p` behaviour — permission-gated tool calls are denied and it replies in text explaining why | pexpect answers `n` to any such prompt |

**Why claude is different**: in `-p` (print/non-interactive) mode, `claude` does not actually emit an interactive `[y/N]`-style prompt on the pty for permission-gated tool calls — it just denies them and explains why in its reply, regardless of what gets typed back on stdin. So `accept` is implemented by passing `--dangerously-skip-permissions` instead (see `app/routes/claude.py`). That flag refuses to run as root, which is why the container runs as a non-root user (`appuser`) — see [System Architecture](#system-architecture).

`agy` and `ollama` still use the original pexpect y/n auto-answer approach from before this was discovered, on the assumption they emit real interactive prompts in print mode — this has **not** been separately verified the way `claude` was, so treat it as unconfirmed for those two.

Use `"reject"` (the default) for untrusted or production workloads where you do not want the LLM to take side-effecting actions automatically.

---

## Testing

### Option A — the `test/` scripts (recommended)

The `test/` directory has one self-contained test script per language, per endpoint, plus a TC-style `suite.*` that runs a fixed set of numbered test cases end-to-end and reports PASS/FAIL:

```
test/
├── bash/    claude.sh   gemini.sh   ollama.sh   suite.sh   (+ _common.sh helper)
├── node/    claude.js   gemini.js   ollama.js   suite.js   (+ _common.js helper)
└── python/  claude.py   gemini.py   ollama.py   suite.py   (+ _common.py helper)
```

**`suite.sh` / `suite.js` / `suite.py`** run 10 test cases against a live instance and exit `0` only if all pass — usable as a CI/smoke-test gate:

```bash
./test/bash/suite.sh
node test/node/suite.js
python3 test/python/suite.py
```

| TC | What it checks |
|---|---|
| TC01 | `GET /health` → 200 + `status: ok` |
| TC02 | Valid token → 200 |
| TC03 | Invalid token → 401 |
| TC04 | `/v1/claude/chat` basic prompt → `success: true` |
| TC05 | `/v1/gemini/chat` (agy) basic prompt → `success: true` |
| TC06 | Claude reports ≥5 available Skills (loose — see [Interactive Mode](#interactive-mode) caveats) |
| TC07 | `interactive_mode: reject` actually blocks the Write tool |
| TC08 | `interactive_mode: accept` actually allows the Write tool |
| TC09 | `/v1/ollama/chat` returns well-formed JSON regardless of whether a real ollama server is reachable |
| TC10 | A short `timeout` bounds the request's wall-clock time |

TC07/TC08 verify the accept/reject divergence by asking claude to write a unique marker string to a file and read it straight back in the *same* request — no need to exec into the container to inspect the filesystem.

The individual per-endpoint scripts below are for quick manual/ad-hoc checks; `suite.*` is for "did I break anything."

Each script:
- Reads `API_TOKEN` (and `OLLAMA_DEFAULT_MODEL` for the ollama scripts) from the project's `.env` file automatically.
- Can be overridden with the `API_TOKEN` / `BASE_URL` environment variables (defaults to `http://localhost:8000`).
- Has no external dependencies beyond what's normally preinstalled: bash uses `curl` (`jq` is optional, used only for pretty-printing), Node uses the built-in global `fetch` (**requires Node 18+**), Python uses the standard-library `urllib` (no `pip install` needed).
- Exits `0` on `"success": true`, `1` otherwise — safe to chain in shell scripts or CI.

Run them directly:

```bash
# claude
./test/bash/claude.sh
node test/node/claude.js
python3 test/python/claude.py

# agy / gemini
./test/bash/gemini.sh
node test/node/gemini.js
python3 test/python/gemini.py

# ollama
./test/bash/ollama.sh
node test/node/ollama.js
python3 test/python/ollama.py
```

Each script accepts positional arguments to override the defaults — pass an empty string `""` to keep a default while overriding a later argument:

```bash
# claude.sh / gemini.sh: [prompt] [interactive_mode] [timeout]
./test/bash/claude.sh "Explain recursion in one sentence." accept 60

# ollama.sh: [prompt] [model] [interactive_mode] [timeout]
./test/bash/ollama.sh "Summarize TCP/IP in 3 bullet points." gemma3
```

```javascript
// node claude.js/gemini.js [prompt] [interactive_mode] [timeout]
node test/node/claude.js "Explain recursion in one sentence." accept 60

// node ollama.js [prompt] [model] [interactive_mode] [timeout]
node test/node/ollama.js "Summarize TCP/IP in 3 bullet points." gemma3
```

```bash
# python claude.py/gemini.py [prompt] [interactive_mode] [timeout]
python3 test/python/claude.py "Explain recursion in one sentence." accept 60

# python ollama.py [prompt] [model] [interactive_mode] [timeout]
python3 test/python/ollama.py "Summarize TCP/IP in 3 bullet points." gemma3
```

> The default test prompt is a short arithmetic question ("What is 2+2?..."). If you see slightly different wording each run ("4.", "2 + 2 = 4.", "Two plus two equals four."), that's normal LLM response variance, not a bug — pass your own prompt as the first argument to test anything else.

### Option B — raw `curl`

```bash
TOKEN="your-api-token-here"   # the API_TOKEN value from .env
BASE="http://localhost:8000"
```

**Health check**

```bash
curl -s $BASE/health
# {"status":"ok"}
```

**Auth check**

```bash
# valid token
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hi"}'

# invalid token -> 401
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer wrong-token" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hi"}'
```

**Claude**

```bash
# default (interactive_mode defaults to reject)
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2 + 2?"}' | jq

# accept mode: auto-confirm tool-use prompts
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "List files in /tmp",
    "interactive_mode": "accept"
  }' | jq

# reject mode: auto-deny confirmation prompts -> check the failure response
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "List files in /tmp",
    "interactive_mode": "reject"
  }' | jq '.success, .exit_code'
```

**Gemini / agy**

```bash
curl -s -X POST $BASE/v1/gemini/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a haiku about Docker."}' | jq

# extract just the response text
curl -s -X POST $BASE/v1/gemini/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain REST API in one sentence."}' | jq -r '.response'
```

**Ollama**

```bash
# explicit model
curl -s -X POST $BASE/v1/ollama/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Summarize TCP/IP in 3 bullet points.",
    "model": "gemma3"
  }' | jq

# omit model -> falls back to OLLAMA_DEFAULT_MODEL
curl -s -X POST $BASE/v1/ollama/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?"}' | jq
```

**Timeout test**

```bash
# short 5s timeout -> a long response should fail
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a 10000 word essay.", "timeout": 5}' | jq '.success, .exit_code'
```

**Multi-line prompt**

```bash
PROMPT=$(cat <<'EOF'
Review this Python code:

def add(a, b):
    return a + b
EOF
)

curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary "$(jq -n --arg p "$PROMPT" '{prompt: $p}')" | jq -r '.response'
```

**Python (using `requests`)**

```python
import requests

BASE = "http://localhost:8000"
HEADERS = {"Authorization": "Bearer your-api-token-here"}

resp = requests.post(
    f"{BASE}/v1/claude/chat",
    headers=HEADERS,
    json={"prompt": "Hello!", "interactive_mode": "reject"},
)
print(resp.json()["response"])
```

---

## Known Issues / Things Still Worth Fixing

- **Manual shell-quoting in `claude.py` / `gemini.py`**: the prompt is escaped with a single `.replace('"', '\\"')` before being handed to `pexpect.spawn()`, which parses the command string with `shlex` (no real shell is invoked, so this is *not* a command-injection risk — unlike the old `ollama.py` bug fixed below). But prompts containing backslashes, unbalanced quotes, or other `shlex`-significant characters can still produce a malformed argv and break the request. The more robust fix, already applied to `ollama.py`, is to spawn the executable with an explicit `args=[...]` list and pass the prompt via stdin instead of interpolating it into the command string.
- **Non-constant-time token comparison** in `app/auth.py` (`credentials.credentials != expected`): fine for a personal/internal server, but a hardened deployment should use `secrets.compare_digest()` to avoid a timing side-channel on the token check.
- **`ANTIGRAVITY_API_KEY`** (documented in `.env.example` as the agy equivalent of the old `GEMINI_API_KEY`) is based on third-party documentation, not confirmed against Google's official Antigravity CLI docs — verify before relying on API-key auth in place of the `~/.gemini` OAuth mount.
- **No TLS or rate limiting built in.** This server is designed to sit behind Docker on a trusted host; if you expose it beyond `localhost`, put a reverse proxy (nginx/Caddy) in front with TLS termination and request throttling.
- **`interactive_mode: accept` is only confirmed working for `/v1/claude/chat`** (via `--dangerously-skip-permissions`, see [Interactive Mode](#interactive-mode)). `/v1/gemini/chat` (agy) and `/v1/ollama/chat` still rely on `cli_runner.py`'s pexpect y/n auto-answer loop, which turned out not to reflect claude's actual `-p` mode behavior — agy/ollama haven't been separately verified and may have the same gap.

---

## Auth Config Volume Mounts

| CLI | Host path | Mount target | Note |
|---|---|---|---|
| claude | `~/.claude.json` | `/mnt/claude-config/claude.json:ro` | copied to `$HOME/.claude.json` by entrypoint.sh |
| claude | `~/.claude/` | `$HOME/.claude:ro` | sessions/history/skills/plugins — mounted at the identical path (not `/root`) so absolute paths baked into `~/.claude/plugins/*.json` stay valid; see [System Architecture](#system-architecture) |
| claude | `~/.agents/` | `$HOME/.agents:ro` | symlink target for some `~/.claude/skills/*` entries (e.g. `hud`, `stitch-design`) — without this they resolve to broken links in the container |
| agy (Antigravity CLI) | `~/.gemini/` | `/mnt/gemini-auth:ro` | copied to writable `$HOME/.gemini` by entrypoint.sh; agy reuses the old Gemini CLI config directory as-is |

The container's `HOME` environment variable is set to match the host's (`environment: HOME=${HOME}` in `docker-compose.yml`) so that `$HOME` above resolves to the same path on both sides.

Mounted as `:ro` (read-only). The container never writes back to your host credentials.

### Mounting extra host paths (gcloud ADC, custom plugin dirs, project directories, ...)

Don't add these to the tracked `docker-compose.yml` — copy `docker-compose.override.yml.example` to `docker-compose.override.yml` instead:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

Then uncomment/add whatever `volumes:` entries you need under the `ai-bridge` service. Docker Compose auto-merges `docker-compose.override.yml` into `docker-compose.yml` with no extra flags — just `docker compose up` as usual. It's already in `.gitignore`, so machine-specific paths never end up committed.

This is the right place for anything a specific host needs that isn't part of the baseline setup every user needs — e.g. gcloud ADC (`~/.config/gcloud`), a plugin's config directory living outside `~/.claude`/`~/.agents`, or a project directory you want the CLI able to read inside the container. Mount it at the identical absolute path (`${HOME}/foo:${HOME}/foo:ro`), not remapped elsewhere, for the same reason `~/.claude` is — see [System Architecture](#system-architecture).

---

## Ollama Host Configuration

The container installs the `ollama` CLI binary but does **not** run the ollama server. It connects to the server on your host.

| Environment | `OLLAMA_HOST` value |
|---|---|
| Linux Docker | `http://172.17.0.1:11434` |
| Docker Desktop (Mac/Win) | `http://host.docker.internal:11434` |

Set this in `.env` before starting the container.

---

## Interactive API Docs

FastAPI provides a built-in Swagger UI at:

```
http://localhost:8000/docs
```

---

## Stopping

```bash
docker compose down
```
