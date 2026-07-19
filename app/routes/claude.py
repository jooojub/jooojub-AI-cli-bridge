import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_token
from app.cli_runner import InteractiveMode, assert_cli_available, run_cli

router = APIRouter(tags=["claude"])


class ChatRequest(BaseModel):
    prompt: str
    interactive_mode: InteractiveMode = InteractiveMode.REJECT
    timeout: int | None = None  # None -> falls back to CLI_TIMEOUT env var, else 120


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

    # req.timeout, when the client sets it, always wins over CLI_TIMEOUT --
    # os.getenv(key, default) only falls back to `default` when the env var
    # is unset, so `os.getenv("CLI_TIMEOUT", req.timeout)` would silently
    # ignore any per-request timeout whenever CLI_TIMEOUT is configured
    # (i.e. always, per .env.example) and use the server-wide value instead.
    timeout = req.timeout if req.timeout is not None else int(os.getenv("CLI_TIMEOUT", 120))

    # -p : print mode (non-interactive output). In print mode, claude does
    # NOT emit an interactive [y/N] prompt for permission-gated tool calls —
    # it just denies them and replies in text, regardless of what we'd type
    # back on stdin. So "accept" is implemented by passing
    # --dangerously-skip-permissions rather than relying on the pexpect y/n
    # auto-answer loop in cli_runner.py (which still handles any other
    # genuine interactive prompts the CLI might emit).
    #
    # req.prompt is passed as its own argv element (args=[...]) rather than
    # interpolated into a quoted string for shlex to reparse -- manual
    # quote-escaping (replace('"', '\\"')) breaks whenever the prompt has an
    # odd number of trailing/adjacent backslashes (e.g. a Windows path or a
    # regex), since shlex then sees an escaped closing quote and raises
    # "No closing quotation".
    cli_args = ["-p"]
    if req.interactive_mode == InteractiveMode.ACCEPT:
        cli_args.append("--dangerously-skip-permissions")
    cli_args.append(req.prompt)

    output, code = run_cli("claude", req.interactive_mode, timeout=timeout, args=cli_args)

    return ChatResponse(
        response=output,
        exit_code=code,
        success=(code == 0),
    )
