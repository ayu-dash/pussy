"""Human-readable and parseable size helpers."""

from __future__ import annotations

import re

_SIZE_UNITS: dict[str, int] = {
    "b": 1,
    "kb": 1024,
    "kib": 1024,
    "mb": 1024**2,
    "mib": 1024**2,
    "gb": 1024**3,
    "gib": 1024**3,
}

_SIZE_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$")


def human_size(size: int) -> str:
    """Format a byte count using binary units."""
    if size < 0:
        raise ValueError("size must be non-negative")
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size)} B"  # pragma: no cover - defensive


def parse_size(value: str | int) -> int:
    """Parse ``"1MB"``, ``"512 KiB"`` or an integer byte count.

    Raises:
        ValueError: if the value is not a valid positive byte count.
    """
    if isinstance(value, int):
        if value < 0:
            raise ValueError("size must be non-negative")
        return value
    match = _SIZE_PATTERN.match(value)
    if not match:
        raise ValueError(f"invalid size: {value!r} (examples: 1048576, 512KB, 2MB)")
    amount = float(match.group(1))
    unit = (match.group(2) or "b").lower()
    if unit not in _SIZE_UNITS:
        raise ValueError(f"unknown size unit: {unit!r}")
    result = int(amount * _SIZE_UNITS[unit])
    if result < 0:
        raise ValueError("size must be non-negative")
    return result
