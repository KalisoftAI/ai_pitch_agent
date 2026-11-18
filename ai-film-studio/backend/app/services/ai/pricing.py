"""Approximate public list prices in USD per 1M tokens."""

PRICING: dict[str, tuple[float, float]] = {
    "gemma": (0.0, 0.0),
    "mock": (0.0, 0.0),
    "gemini-2.5-flash-lite": (0.075, 0.30),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "claude-opus-4-5": (15.00, 75.00),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_price, output_price = PRICING.get(model, (0.0, 0.0))
    cost = (prompt_tokens / 1_000_000) * input_price
    cost += (completion_tokens / 1_000_000) * output_price
    return round(cost, 6)
