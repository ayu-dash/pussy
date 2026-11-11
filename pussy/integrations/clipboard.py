"""Cross-platform clipboard integration."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClipboardResult:
    """Outcome of one clipboard attempt."""

    success: bool
    command: str = ""
    error: str = ""


class ClipboardManager:
    """Copy text to the native clipboard without assuming success.

    The runner and executable lookup are injectable so clipboard behaviour can
    be tested on every platform from any host.
    """

    def __init__(
        self,
        platform: str | None = None,
        *,
        environment: dict[str, str] | None = None,
        which: Callable[[str], str | None] = shutil.which,
        runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
        timeout: int = 30,
    ) -> None:
        self.platform = platform or sys.platform
        self.environment = environment if environment is not None else os.environ
        self.which = which
        self.runner = runner
        self.timeout = timeout

    def candidates(self) -> list[tuple[list[str], str]]:
        """Return platform command candidates in preferred order."""
        if self.platform == "win32":
            return [
                (["clip"], "utf-16-le"),
                (
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Set-Clipboard"],
                    "utf-8",
                ),
            ]
        if self.platform == "darwin":
            return [(["pbcopy"], "utf-8")]
        candidates: list[tuple[list[str], str]] = []
        session = self.environment.get("XDG_SESSION_TYPE", "").lower()
        if self.environment.get("WAYLAND_DISPLAY") or session == "wayland":
            candidates.append((["wl-copy"], "utf-8"))
        candidates.extend(
            [
                (["xclip", "-selection", "clipboard"], "utf-8"),
                (["xsel", "--clipboard", "--input"], "utf-8"),
            ]
        )
        if not self.environment.get("WAYLAND_DISPLAY") and session != "wayland":
            candidates.append((["wl-copy"], "utf-8"))
        return candidates

    def copy(self, text: str) -> ClipboardResult:
        """Try each candidate until one exits successfully."""
        errors: list[str] = []
        for command, encoding in self.candidates():
            executable = command[0]
            if self.which(executable) is None:
                errors.append(f"{executable}: not installed")
                continue
            try:
                completed = self.runner(
                    command,
                    input=text.encode(encoding, errors="replace"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=self.timeout,
                    check=False,
                )
            except (FileNotFoundError, PermissionError, OSError) as exc:
                errors.append(f"{executable}: {exc}")
                continue
            except subprocess.TimeoutExpired:
                errors.append(f"{executable}: timed out")
                continue
            if completed.returncode == 0:
                return ClipboardResult(True, " ".join(command))
            stderr = getattr(completed, "stderr", b"") or b""
            if isinstance(stderr, bytes):
                detail = stderr.decode("utf-8", errors="replace").strip()
            else:
                detail = str(stderr).strip()
            errors.append(
                f"{executable}: exited with {completed.returncode}"
                + (f" ({detail[:200]})" if detail else "")
            )
        return ClipboardResult(False, "", "; ".join(errors) or "no clipboard utility available")
