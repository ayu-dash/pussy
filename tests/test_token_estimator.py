"""Token estimation tests."""

from __future__ import annotations

from pussy.core.token_estimator import TokenEstimator


def test_empty_text() -> None:
    estimate = TokenEstimator().estimate("")
    assert estimate.characters == 0
    assert estimate.words == 0
    assert estimate.lines == 0
    assert estimate.tokens == 0
    assert estimate.approximate


def test_character_approximation() -> None:
    estimate = TokenEstimator(tokenizer="approximate").estimate("abcdefgh")
    assert estimate.tokens == 2
    assert estimate.tokenizer == "approximate"
    assert "characters / 4" in estimate.method


def test_words_and_lines() -> None:
    estimate = TokenEstimator().estimate("hello world\nsecond line\n")
    assert estimate.words == 4
    assert estimate.lines == 2
    assert estimate.bytes == len(b"hello world\nsecond line\n")


def test_unknown_model_falls_back_with_label() -> None:
    estimate = TokenEstimator(model="some-unknown-model").estimate("hello world")
    assert estimate.approximate
    assert estimate.tokens == 3


def test_forced_tiktoken_without_package_is_labelled() -> None:
    estimate = TokenEstimator(tokenizer="tiktoken").estimate("hello world")
    assert estimate.approximate
    assert "tiktoken" in estimate.tokenizer
