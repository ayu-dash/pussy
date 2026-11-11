"""Clipboard integration tests using injected runners."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from pussy.integrations.clipboard import ClipboardManager


@dataclass
class Completed:
    returncode: int
    stderr: bytes = b""


class Recorder:
    def __init__(self, returncodes: dict[str, int] | None = None) -> None:
        self.calls: list[tuple[list[str], bytes]] = []
        self.returncodes = returncodes or {}

    def __call__(self, command: list[str], **kwargs: object) -> Completed:
        self.calls.append((command, kwargs.get("input", b"")))  # type: ignore[arg-type]
        return Completed(self.returncodes.get(command[0], 0))


def which_available(*commands: str):
    def _which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in commands else None

    return _which


def test_successful_copy_reports_command() -> None:
    recorder = Recorder()
    manager = ClipboardManager("darwin", which=which_available("pbcopy"), runner=recorder)
    result = manager.copy("hello")
    assert result.success
    assert result.command == "pbcopy"
    assert recorder.calls[0][1] == b"hello"


def test_unavailable_command_falls_back() -> None:
    recorder = Recorder()
    manager = ClipboardManager(
        "linux",
        environment={},
        which=which_available("xclip"),
        runner=recorder,
    )
    result = manager.copy("hello")
    assert result.success
    assert result.command.startswith("xclip")
    assert [call[0][0] for call in recorder.calls] == ["xclip"]


def test_all_commands_unavailable() -> None:
    manager = ClipboardManager("linux", environment={}, which=which_available(), runner=Recorder())
    result = manager.copy("hello")
    assert not result.success
    assert "not installed" in result.error


def test_failed_command_is_not_reported_as_success() -> None:
    recorder = Recorder({"xclip": 1, "xsel": 1})
    manager = ClipboardManager(
        "linux",
        environment={},
        which=which_available("xclip", "xsel"),
        runner=recorder,
    )
    result = manager.copy("hello")
    assert not result.success
    assert "exited with 1" in result.error


def test_fallback_after_failure() -> None:
    recorder = Recorder({"xclip": 1, "xsel": 0})
    manager = ClipboardManager(
        "linux",
        environment={},
        which=which_available("xclip", "xsel"),
        runner=recorder,
    )
    result = manager.copy("hello")
    assert result.success
    assert result.command.startswith("xsel")
    assert len(recorder.calls) == 2


def test_wayland_prefers_wl_copy() -> None:
    recorder = Recorder()
    manager = ClipboardManager(
        "linux",
        environment={"WAYLAND_DISPLAY": "wayland-0", "XDG_SESSION_TYPE": "wayland"},
        which=which_available("wl-copy", "xclip"),
        runner=recorder,
    )
    result = manager.copy("hi")
    assert result.success
    assert result.command == "wl-copy"


def test_linux_orders_wl_copy_last_on_x11() -> None:
    manager = ClipboardManager("linux", environment={"DISPLAY": ":0"})
    commands = [command[0] for command, _encoding in manager.candidates()]
    assert commands[0] == "xclip"
    assert commands[-1] == "wl-copy"


def test_windows_uses_clip_with_utf16() -> None:
    recorder = Recorder()
    manager = ClipboardManager("win32", which=which_available("clip"), runner=recorder)
    result = manager.copy("héllo")
    assert result.success
    assert result.command == "clip"
    assert recorder.calls[0][1] == "héllo".encode("utf-16-le")


def test_runner_exception_falls_back() -> None:
    class Exploding:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, command: list[str], **kwargs: object) -> Completed:
            self.calls += 1
            if command[0] == "xclip":
                raise OSError("display unavailable")
            return Completed(0)

    exploding = Exploding()
    manager = ClipboardManager(
        "linux",
        environment={},
        which=which_available("xclip", "xsel"),
        runner=exploding,
    )
    result = manager.copy("hello")
    assert result.success
    assert result.command.startswith("xsel")


def test_timeout_is_reported(monkeypatch) -> None:
    def timeout(*args: object, **kwargs: object):
        raise subprocess.TimeoutExpired(cmd="xclip", timeout=1)

    manager = ClipboardManager(
        "linux", environment={}, which=which_available("xclip"), runner=timeout
    )
    result = manager.copy("hello")
    assert not result.success
    assert "timed out" in result.error
