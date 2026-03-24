import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_token
from app.cli_runner import InteractiveMode, assert_cli_available, run_cli

router = APIRouter(tags=["claude"])


class ChatRequest(BaseModel):
    prompt: str
    interactive_mode: InteractiveMode = InteractiveMode.REJECT
    timeout: int = 120


class ChatResponse(BaseModel):
    llm: str = "claude"
    response: str
    exit_code: int
    success: bool


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, _token: str = Depends(verify_token)) -> ChatResponse:
    try:
        assert_cli_available("claude")
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    timeout = int(os.getenv("CLI_TIMEOUT", req.timeout))

    # -p  : print mode (non-interactive output, still honours tool-use prompts)
    # --   : separates flags from the prompt safely
    escaped = req.prompt.replace('"', '\\"')
    cmd = f'claude -p "{escaped}"'

    output, code = run_cli(cmd, req.interactive_mode, timeout=timeout)

    return ChatResponse(
        response=output,
        exit_code=code,
        success=(code == 0),
    )
