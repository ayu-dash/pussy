"""Safe text decoding and binary detection utilities.

The functions here are intentionally dependency-free.  They never modify input
files and never raise for malformed data: decoding failures fall back to a
lossless single-byte encoding, while binary data is reported explicitly.
"""

from __future__ import annotations

import codecs

_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)

_FALLBACK_ENCODINGS = ("cp1252", "latin-1")

_ALLOWED_CONTROL = frozenset({9, 10, 11, 12, 13, 27})


def detect_bom_encoding(data: bytes) -> str | None:
    """Return the encoding implied by a byte-order mark, if any."""
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            return encoding
    return None


def looks_binary(data: bytes, *, sample_size: int = 8192) -> bool:
    """Heuristically decide whether *data* is binary.

    A NUL byte that is not part of a Unicode BOM marks the sample as binary.
    Control characters above a small ratio are treated as binary as well.
    """
    if not data:
        return False
    if detect_bom_encoding(data) is not None:
        return False

    sample = data[:sample_size]
    if b"\x00" in sample:
        return True

    control_count = sum(1 for byte in sample if byte < 32 and byte not in _ALLOWED_CONTROL)
    # A high ratio of invalid UTF-8 sequences with many high bytes is typical
    # for compressed/executable content, but plain legacy text (cp1252) must
    # remain readable.  Do not reject on high bytes alone.
    return control_count / len(sample) > 0.10


def decode_bytes(data: bytes) -> tuple[str, str]:
    """Decode bytes to text using the safest available encoding.

    Returns a ``(text, encoding)`` tuple.  UTF BOMs are honoured, UTF-8 is
    preferred, and common legacy encodings act as a lossless fallback.
    """
    if not data:
        return "", "utf-8"

    bom_encoding = detect_bom_encoding(data)
    candidates: list[str] = []
    if bom_encoding:
        candidates.append(bom_encoding)
    if b"\x00" in data[:4] and bom_encoding is None:
        # UTF-16 without a BOM: infer byte order from NUL placement.
        candidates.extend(("utf-16-le", "utf-16-be"))
    candidates.extend(("utf-8", "utf-8-sig", *_FALLBACK_ENCODINGS))

    for encoding in dict.fromkeys(candidates):
        try:
            return data.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue

    # latin-1 cannot fail, but keep a defensive final branch.
    return data.decode("latin-1", errors="replace"), "latin-1"


def normalize_newlines(text: str) -> str:
    """Convert CRLF/CR line endings to LF without touching other characters."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def count_lines(text: str) -> int:
    """Count logical lines; an empty string has zero lines."""
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)
