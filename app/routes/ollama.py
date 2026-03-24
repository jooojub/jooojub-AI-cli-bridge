import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_token
from app.cli_runner import InteractiveMode, assert_cli_available, run_cli

router = APIRouter(tags=["ollama"])

_DEFAULT_MODEL = "llama3.2"


class ChatRequest(BaseModel):
    prompt: str
    model: str | None = None          # falls back to OLLAMA_DEFAULT_MODEL env var
    interactive_mode: InteractiveMode = InteractiveMode.REJECT
    timeout: int = 120


class ChatResponse(BaseModel):
    llm: str = "ollama"
    model: str
    response: str
    exit_code: int
    success: bool


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, _token: str = Depends(verify_token)) -> ChatResponse:
    try:
        assert_cli_available("ollama")
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    model = req.model or os.getenv("OLLAMA_DEFAULT_MODEL", _DEFAULT_MODEL)
    timeout = int(os.getenv("CLI_TIMEOUT", req.timeout))

    # Pass the prompt via stdin: echo "prompt" | ollama run MODEL
    # This avoids shell-quoting edge-cases with complex prompts.
    escaped_prompt = req.prompt.replace("'", "'\\''")
    escaped_model = model.replace('"', '\\"')
    cmd = f"bash -c 'echo \"{escaped_prompt}\" | ollama run \"{escaped_model}\"'"

    output, code = run_cli(cmd, req.interactive_mode, timeout=timeout)

    return ChatResponse(
        model=model,
        response=output,
        exit_code=code,
        success=(code == 0),
    )
