"""
Run CLI tools and handle interactive y/n prompts automatically.

accept mode  → respond 'y' to every confirmation prompt
reject mode  → respond 'n' (the CLI will usually abort/fail)
"""

import re
import shutil
from enum import Enum

import pexpect


class InteractiveMode(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"


# Regex patterns that indicate the CLI is waiting for a y/n confirmation.
# Add more patterns here as you encounter new prompts from specific CLIs.
_PROMPT_PATTERNS: list[str] = [
    r"\[y/N\]",
    r"\[Y/n\]",
    r"\[yes/no\]",
    r"\(y/n\)",
    r"\(yes/no\)",
    r"continue\?",
    r"Allow\?",
    r"proceed\?",
    r"Do you want to",
    r"Are you sure",
    r"Press Enter to continue",
]

_ANSI_ESCAPE = re.compile(
    r"\x1B(?:"
    r"\[[0-?]*[ -/]*[@-~]"                   # CSI sequences (ESC [ ... )
    r"|\][^\x07\x1B]*(?:\x07|\x1B\\)"        # OSC sequences (ESC ] ... BEL/ST)
    r"|[PX^_][^\x1B]*\x1B\\"                 # DCS / SOS / PM / APC (ESC P/X/^/_ ... ST)
    r"|[@-Z\\-_]"                             # Fe sequences (ESC X), tried after the specific forms above
    r"|[ -/]*[0-~]"                          # nF sequences, e.g. charset select (ESC ( B), ESC 7 / ESC 8
    r")"
)
# Remaining non-printable control characters (except \t \n \r)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def _strip_ansi(text: str) -> str:
    text = _ANSI_ESCAPE.sub("", text)
    text = _CONTROL_CHARS.sub("", text)
    return text


def run_cli(
    cmd: str,
    mode: InteractiveMode,
    timeout: int = 120,
    args: list[str] | None = None,
    stdin_data: str | None = None,
) -> tuple[str, int]:
    """
    Spawn *cmd* in a pseudo-TTY and respond to every interactive prompt
    according to *mode*.

    If *args* is given, *cmd* is treated as an executable and *args* as its
    argv, run directly with no shell involved (safe for untrusted input).
    Otherwise *cmd* is parsed with shlex, still without invoking a shell.

    If *stdin_data* is given, it is written as a single line followed by
    EOF right after spawning, equivalent to piping it in like
    `echo "stdin_data" | cmd`.

    Returns (output_text, exit_code).
    """
    try:
        child = pexpect.spawn(
            cmd,
            args=args or [],
            timeout=timeout,
            encoding="utf-8",
            codec_errors="replace",
        )

        if stdin_data is not None:
            child.sendline(stdin_data)
            child.sendeof()

        patterns = _PROMPT_PATTERNS + [pexpect.EOF, pexpect.TIMEOUT]
        eof_idx = len(_PROMPT_PATTERNS)
        timeout_idx = eof_idx + 1

        output_parts: list[str] = []

        while True:
            try:
                idx = child.expect(patterns, timeout=timeout)
                output_parts.append(child.before or "")

                if idx == eof_idx:
                    break

                if idx == timeout_idx:
                    child.close(force=True)
                    break

                # A confirmation prompt was matched — include it in output
                output_parts.append(child.after or "")

                if mode == InteractiveMode.ACCEPT:
                    child.sendline("y")
                else:
                    child.sendline("n")

            except pexpect.EOF:
                output_parts.append(child.before or "")
                break
            except pexpect.TIMEOUT:
                output_parts.append(child.before or "")
                child.close(force=True)
                break

        child.close()
        exit_code = child.exitstatus if child.exitstatus is not None else 0

    except pexpect.exceptions.ExceptionPexpect as exc:
        return f"pexpect error: {exc}", 1
    except Exception as exc:  # noqa: BLE001
        return f"Unexpected error: {exc}", 1

    raw = "".join(output_parts)
    return _strip_ansi(raw).strip(), exit_code


def assert_cli_available(name: str) -> None:
    """Raise RuntimeError if *name* is not on PATH."""
    if shutil.which(name) is None:
        raise RuntimeError(
            f"'{name}' CLI not found on PATH. "
            "Make sure it is installed inside the container."
        )
