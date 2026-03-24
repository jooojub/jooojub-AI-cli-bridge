# AI CLI Bridge

RESTful API server that proxies requests to **claude**, **gemini**, and **ollama** CLIs running inside a Docker container.

- Bearer token authentication via `.env`
- Two interactive modes: auto-accept or auto-reject CLI confirmation prompts
- OAuth credentials mounted read-only from the host

---

## Requirements

- Docker & Docker Compose
- Host machine with **claude**, **gemini**, and/or **ollama** already authenticated
- (Ollama) ollama server running on the host

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
  --add-host host.docker.internal:host-gateway \
  -v "$HOME/.claude:/root/.claude:ro" \
  -v "$HOME/.config/gemini:/root/.config/gemini:ro" \
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

Same fields as `/v1/claude/chat`.

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

Some CLI tools ask for confirmation when performing actions (e.g., tool use, file access, code execution):

| Mode | Behaviour |
|---|---|
| `"accept"` | Responds `y` to every `[y/N]` / `Allow?` / `proceed?` prompt |
| `"reject"` | Responds `n` — the CLI will usually abort and return a non-zero exit code |

Use `"reject"` (the default) for untrusted or production workloads where you do not want the LLM to take side-effecting actions automatically.

---

## Usage Examples

### curl

```bash
TOKEN="your-api-token-here"

# Claude
curl -s -X POST http://localhost:8000/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2 + 2?", "interactive_mode": "reject"}' | jq

# Gemini
curl -s -X POST http://localhost:8000/v1/gemini/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a haiku about Docker."}' | jq

# Ollama (specify model)
curl -s -X POST http://localhost:8000/v1/ollama/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarise TCP/IP in 3 bullet points.", "model": "gemma3"}' | jq
```

### Python

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

## Auth Config Volume Mounts

| CLI | Host path | Container path |
|---|---|---|
| claude | `~/.claude` | `/root/.claude` |
| gemini | `~/.config/gemini` | `/root/.config/gemini` |
| gcloud ADC | `~/.config/gcloud` | `/root/.config/gcloud` |

Mounted as `:ro` (read-only). The container never writes back to your host credentials.

For gcloud ADC, uncomment the relevant line in `docker-compose.yml`.

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
