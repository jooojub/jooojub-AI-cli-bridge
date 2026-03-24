import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_token
from app.cli_runner import InteractiveMode, assert_cli_available, run_cli

router = APIRouter(tags=["gemini"])


class ChatRequest(BaseModel):
    prompt: str
    interactive_mode: InteractiveMode = InteractiveMode.REJECT
    timeout: int = 120


class ChatResponse(BaseModel):
    llm: str = "gemini"
    response: str
    exit_code: int
    success: bool


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, _token: str = Depends(verify_token)) -> ChatResponse:
    try:
        assert_cli_available("gemini")
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    timeout = int(os.getenv("CLI_TIMEOUT", req.timeout))

    # gemini CLI: non-interactive print mode via -p flag
    escaped = req.prompt.replace('"', '\\"')
    cmd = f'gemini -p "{escaped}"'

    output, code = run_cli(cmd, req.interactive_mode, timeout=timeout)

    return ChatResponse(
        response=output,
        exit_code=code,
        success=(code == 0),
    )
