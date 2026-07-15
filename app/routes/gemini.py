import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_token
from app.cli_runner import InteractiveMode, assert_cli_available, run_cli

router = APIRouter(tags=["gemini"])


class ChatRequest(BaseModel):
    prompt: str
    interactive_mode: InteractiveMode = InteractiveMode.REJECT
    timeout: int | None = None  # None -> falls back to CLI_TIMEOUT env var, else 120


class ChatResponse(BaseModel):
    llm: str = "gemini"
    response: str
    exit_code: int
    success: bool


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, _token: str = Depends(verify_token)) -> ChatResponse:
    try:
        assert_cli_available("agy")
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    # See claude.py for why req.timeout must be checked before falling back
    # to CLI_TIMEOUT rather than passed as os.getenv's default.
    timeout = req.timeout if req.timeout is not None else int(os.getenv("CLI_TIMEOUT", 120))

    # Antigravity CLI (agy), the Gemini CLI successor: non-interactive
    # print mode via -p flag, same as the old `gemini -p` invocation.
    escaped = req.prompt.replace('"', '\\"')
    cmd = f'agy -p "{escaped}"'

    output, code = run_cli(cmd, req.interactive_mode, timeout=timeout)

    return ChatResponse(
        response=output,
        exit_code=code,
        success=(code == 0),
    )
