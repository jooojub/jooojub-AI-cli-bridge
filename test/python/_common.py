"""Shared helpers for the python test scripts. Not meant to be run directly.

Uses only the standard library (urllib) so there is no pip install needed.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


def _load_env_file() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def get_config() -> dict:
    env = _load_env_file()
    return {
        "base_url": os.environ.get("BASE_URL", "http://localhost:8000"),
        "api_token": os.environ.get("API_TOKEN", env.get("API_TOKEN", "your-secret-token-here")),
        "ollama_default_model": os.environ.get(
            "OLLAMA_DEFAULT_MODEL", env.get("OLLAMA_DEFAULT_MODEL", "llama3.2")
        ),
    }


def post_chat(endpoint: str, body: dict, token: str | None = None) -> tuple[int, dict]:
    config = get_config()
    url = f"{config['base_url']}{endpoint}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token or config['api_token']}",
            "Content-Type": "application/json",
        },
    )
    request_timeout = body.get("timeout", 30) + 10
    try:
        with urllib.request.urlopen(req, timeout=request_timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8") or "{}"
        return exc.code, json.loads(payload)


def get_json(endpoint: str) -> tuple[int, dict]:
    config = get_config()
    url = f"{config['base_url']}{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8") or "{}"
        return exc.code, json.loads(payload)


def print_result(status: int, payload: dict) -> None:
    print(f"HTTP {status}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
