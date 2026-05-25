"""litellm wrapper: structured JSON calls + cost estimation.

The pipeline is inherently sequential (primary -> adversarial -> orchestrator), so there
is nothing to parallelize within a round — calls are plain synchronous completions.
"""

import json
from typing import Type, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# Rough output-token budgets per role, for pre-run cost estimation only.
OUTPUT_TOKEN_BUDGET = {
    "primary": 1500,
    "adversarial": 2000,
    "orchestrator": 1800,
}


class ModelError(RuntimeError):
    pass


def model_string(provider: str, model: str) -> str:
    """litellm routing string. Prefixing with the provider is accepted for all three."""
    return f"{provider}/{model}"


def call_structured(
    provider: str,
    model: str,
    system: str,
    user: str,
    schema: Type[T],
) -> T:
    """One completion that must return JSON matching `schema`. One repair retry, then fail."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            resp = litellm.completion(
                model=model_string(provider, model),
                messages=messages,
                response_format={"type": "json_object"},
            )
        except Exception as e:  # network / provider / auth failures
            raise ModelError(f"{provider}/{model} call failed: {e}") from e

        content = resp.choices[0].message.content or ""
        try:
            data = json.loads(content)
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            # Feed the error back once so the model can repair its output.
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response did not match the required JSON schema. "
                        f"Error: {e}. Return ONLY valid JSON matching the schema, nothing else."
                    ),
                }
            )

    raise ModelError(
        f"{provider}/{model} did not return schema-valid JSON after a retry: {last_error}"
    )


def _rate(model: str, provider: str) -> tuple[float, float]:
    """(input_cost_per_token, output_cost_per_token) from litellm's cost map, or (0, 0)."""
    cost_map = litellm.model_cost
    for key in (model, model_string(provider, model)):
        entry = cost_map.get(key)
        if entry:
            return (
                entry.get("input_cost_per_token", 0.0) or 0.0,
                entry.get("output_cost_per_token", 0.0) or 0.0,
            )
    return (0.0, 0.0)


def estimate_input_tokens(model: str, provider: str, text: str) -> int:
    try:
        return litellm.token_counter(
            model=model_string(provider, model),
            messages=[{"role": "user", "content": text}],
        )
    except Exception:
        return max(1, len(text) // 4)  # ~4 chars/token fallback


def estimate_cost(model: str, provider: str, role: str, input_text: str) -> float:
    in_tok = estimate_input_tokens(model, provider, input_text)
    out_tok = OUTPUT_TOKEN_BUDGET.get(role, 1500)
    in_rate, out_rate = _rate(model, provider)
    return in_tok * in_rate + out_tok * out_rate
