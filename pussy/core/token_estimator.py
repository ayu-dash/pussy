"""Token estimation with optional model tokenizers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from pussy.utils.encoding import count_lines


@dataclass(frozen=True, slots=True)
class TokenEstimate:
    """Token and text statistics for one document."""

    characters: int
    words: int
    lines: int
    bytes: int
    tokens: int
    tokenizer: str
    method: str
    approximate: bool


class TokenEstimator:
    """Estimate token counts without requiring a network or API key.

    ``auto`` uses ``tiktoken`` when it is installed *and* the requested model is
    known to it.  Otherwise a labelled character-based approximation is used.
    """

    def __init__(self, model: str | None = None, tokenizer: str = "auto") -> None:
        self.model = model
        self.tokenizer = tokenizer

    def estimate(self, text: str) -> TokenEstimate:
        """Measure *text* and estimate its token count."""
        characters = len(text)
        words = len(text.split())
        lines = count_lines(text)
        size = len(text.encode("utf-8"))

        if self.tokenizer in {"auto", "tiktoken"} and self.model:
            tokens = self._tiktoken_count(text)
            if tokens is not None:
                return TokenEstimate(
                    characters=characters,
                    words=words,
                    lines=lines,
                    bytes=size,
                    tokens=tokens,
                    tokenizer=f"tiktoken:{self.model}",
                    method="tokenizer",
                    approximate=False,
                )

        tokens = math.ceil(characters / 4) if characters else 0
        method = "approximate (characters / 4)"
        tokenizer_name = "approximate"
        if self.tokenizer == "tiktoken":
            tokenizer_name = "approximate (tiktoken unavailable or model unknown)"
        return TokenEstimate(
            characters=characters,
            words=words,
            lines=lines,
            bytes=size,
            tokens=tokens,
            tokenizer=tokenizer_name,
            method=method,
            approximate=True,
        )

    def _tiktoken_count(self, text: str) -> int | None:
        try:
            import tiktoken  # type: ignore[import-not-found]
        except ImportError:
            return None
        try:
            encoding = tiktoken.encoding_for_model(self.model or "")
            return len(encoding.encode(text, disallowed_special=()))
        except (KeyError, ValueError):
            return None
        except Exception:  # defensive: a tokenizer bug must not break generation
            return None
