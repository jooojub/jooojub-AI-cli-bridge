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

### 0. 공통 변수 설정

```bash
TOKEN="your-api-token-here"   # .env의 API_TOKEN 값
BASE="http://localhost:8000"
```

---

### 1. 서버 상태 확인

```bash
curl -s $BASE/health
# {"status":"ok"}
```

---

### 2. 인증 토큰 테스트

```bash
# 올바른 토큰
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hi"}'

# 잘못된 토큰 → 401
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer wrong-token" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hi"}'
```

---

### 3. Claude

```bash
# 기본 질문 (interactive_mode 기본값: reject)
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2 + 2?"}' | jq

# accept 모드: 도구 사용 허용 확인 프롬프트에 자동 yes
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "List files in /tmp",
    "interactive_mode": "accept"
  }' | jq

# reject 모드: 확인 프롬프트에 자동 no → 실패 응답 확인
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "List files in /tmp",
    "interactive_mode": "reject"
  }' | jq '.success, .exit_code'
```

---

### 4. Gemini

```bash
curl -s -X POST $BASE/v1/gemini/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a haiku about Docker."}' | jq

# 응답 텍스트만 추출
curl -s -X POST $BASE/v1/gemini/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain REST API in one sentence."}' | jq -r '.response'
```

---

### 5. Ollama

```bash
# 모델 지정
curl -s -X POST $BASE/v1/ollama/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Summarise TCP/IP in 3 bullet points.",
    "model": "gemma3"
  }' | jq

# 모델 생략 → OLLAMA_DEFAULT_MODEL 사용
curl -s -X POST $BASE/v1/ollama/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?"}' | jq
```

---

### 6. 타임아웃 테스트

```bash
# timeout을 5초로 짧게 설정 → 긴 응답은 실패하는지 확인
curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a 10000 word essay.", "timeout": 5}' | jq '.success, .exit_code'
```

---

### 7. 멀티라인 프롬프트

```bash
PROMPT=$(cat <<'EOF'
다음 Python 코드를 리뷰해줘:

def add(a, b):
    return a + b
EOF
)

curl -s -X POST $BASE/v1/claude/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary "$(jq -n --arg p "$PROMPT" '{prompt: $p}')" | jq -r '.response'
```

---

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
