"""Config loading and validation.

Enforces the PRD's config rules in code (not just schema):
- at least 2 providers configured
- every role maps to a configured provider
- primary != adversarial provider (hard error - cross-model pressure is the premise)
- rounds 1..MAX_ROUNDS, with MAX_ROUNDS a hard cap that config cannot exceed
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError, model_validator

MAX_ROUNDS = 4  # hard cap, enforced here regardless of config


def model_family(model: str) -> str:
    """Collapse a model ID to its underlying model family.

    Works for direct IDs ("claude-fable-5", "gpt-5.6-sol") and gateway slugs
    ("openai/gpt-5.6-terra" via OpenRouter), so the primary/adversarial
    different-family rule holds even when a debater is routed through a gateway.
    Unknown IDs return themselves, so they never collide unless identical.
    """
    s = model.lower()
    if "claude" in s or "anthropic" in s:
        return "anthropic"
    if "gpt" in s or "openai" in s:
        return "openai"
    if "gemini" in s or "google" in s:
        return "gemini"
    return s


class ConfigError(ValueError):
    """Raised when a config file is structurally valid YAML but breaks a MARS rule."""


class Provider(BaseModel):
    model: str


class Roles(BaseModel):
    primary: str
    adversarial: str
    orchestrator: str


class Rounds(BaseModel):
    default: int = 2
    max: int = MAX_ROUNDS


class Config(BaseModel):
    providers: dict[str, Provider]
    roles: Roles
    rounds: Rounds = Rounds()

    @model_validator(mode="after")
    def _validate(self) -> "Config":
        configured = set(self.providers.keys())

        if len(configured) < 2:
            raise ConfigError(
                f"At least 2 providers must be configured (found {len(configured)}: "
                f"{sorted(configured) or 'none'})."
            )

        for role_name in ("primary", "adversarial", "orchestrator"):
            provider_key = getattr(self.roles, role_name)
            if provider_key not in configured:
                raise ConfigError(
                    f"Role '{role_name}' is assigned to provider '{provider_key}', "
                    f"which is not configured. Configured providers: {sorted(configured)}."
                )

        if self.roles.primary == self.roles.adversarial:
            raise ConfigError(
                f"primary and adversarial must be different providers (both are "
                f"'{self.roles.primary}'). The two debaters must be peers from different "
                f"families, or you get correlated blind spots. Assign them to different providers."
            )

        primary_model = self.providers[self.roles.primary].model
        adversarial_model = self.providers[self.roles.adversarial].model
        if model_family(primary_model) == model_family(adversarial_model):
            raise ConfigError(
                f"primary ({self.roles.primary}: {primary_model}) and adversarial "
                f"({self.roles.adversarial}: {adversarial_model}) resolve to the same model "
                f"family ('{model_family(primary_model)}'). The two debaters must be peers from "
                f"different families - even when routed through a gateway like OpenRouter - or "
                f"you get correlated blind spots."
            )

        if self.rounds.max > MAX_ROUNDS:
            raise ConfigError(
                f"rounds.max is {self.rounds.max}, but the hard cap is {MAX_ROUNDS}."
            )
        if not (1 <= self.rounds.default <= self.rounds.max):
            raise ConfigError(
                f"rounds.default ({self.rounds.default}) must be between 1 and "
                f"rounds.max ({self.rounds.max})."
            )

        return self

    def model_for(self, role_name: str) -> str:
        """Return the model ID assigned to a role."""
        provider_key = getattr(self.roles, role_name)
        return self.providers[provider_key].model

    def provider_for(self, role_name: str) -> str:
        return getattr(self.roles, role_name)


def validate_config(data: dict) -> Config:
    """Validate a config dict, unwrapping pydantic errors into a flat ConfigError."""
    try:
        return Config.model_validate(data)
    except ValidationError as e:
        msgs = [err["msg"].removeprefix("Value error, ") for err in e.errors()]
        raise ConfigError("; ".join(msgs)) from None


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    return validate_config(data)
