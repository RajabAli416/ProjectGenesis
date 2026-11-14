"""Context budgeting. Converts the model's context window into per-section character allowances so
prompts never overflow; measured prompt_eval_count feeds back to tighten the chars-per-token ratio."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_CHARS_PER_TOKEN = 3.6


@dataclass
class Budget:
    num_ctx: int
    num_predict: int
    chars_per_token: float = DEFAULT_CHARS_PER_TOKEN
    safety: float = 0.85

    @property
    def input_chars(self) -> int:
        tokens = max(256, int((self.num_ctx - self.num_predict) * self.safety))
        return int(tokens * self.chars_per_token)

    def section(self, fraction: float, minimum: int = 200) -> int:
        return max(minimum, int(self.input_chars * fraction))


class RatioEstimator:
    """Running estimate of chars/token from (prompt chars, prompt_eval_count) observations."""

    def __init__(self, initial: float = DEFAULT_CHARS_PER_TOKEN) -> None:
        self.value = initial
        self.samples = 0

    def observe(self, chars: int, tokens: int | None) -> None:
        if not tokens or tokens <= 0 or chars <= 0:
            return
        ratio = chars / tokens
        self.samples += 1
        alpha = 0.2 if self.samples > 3 else 0.5
        self.value = max(2.0, min(6.0, self.value * (1 - alpha) + ratio * alpha))


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"
