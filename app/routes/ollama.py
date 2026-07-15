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
    timeout: int | None = None  # None -> falls back to CLI_TIMEOUT env var, else 120


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
    # See claude.py for why req.timeout must be checked before falling back
    # to CLI_TIMEOUT rather than passed as os.getenv's default.
    timeout = req.timeout if req.timeout is not None else int(os.getenv("CLI_TIMEOUT", 120))

    # Run `ollama run MODEL PROMPT` directly (no shell, prompt as its own
    # argv element -- avoids command injection same as before, but also
    # avoids feeding the prompt via stdin: `child.sendline()` writes any
    # newlines embedded in the prompt as-is, which a line-based stdin reader
    # would see as multiple separate turns instead of one multi-line message).
    output, code = run_cli(
        "ollama",
        req.interactive_mode,
        timeout=timeout,
        args=["run", model, req.prompt],
    )

    return ChatResponse(
        model=model,
        response=output,
        exit_code=code,
        success=(code == 0),
    )
