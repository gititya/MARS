"""Load provider API keys from the macOS Keychain into the environment.

Keys are stored as generic passwords under account 'mars', with the service name
equal to the provider's environment variable (e.g. service 'ANTHROPIC_API_KEY').
This keeps keys encrypted at rest and scoped to MARS: nothing is exported globally
and nothing is written to disk in plaintext.

A Keychain entry under account 'mars' takes precedence over an ambient shell variable,
so a dedicated MARS key always wins over a stale or shared global key. If no Keychain
entry exists, MARS falls back to the shell environment (useful on CI / non-macOS).
"""

import os
import subprocess

from mars.config import Config

PROVIDER_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
KEYCHAIN_ACCOUNT = "mars"


def keychain_get(service: str, account: str = KEYCHAIN_ACCOUNT) -> str | None:
    """Return the stored secret, or None if absent / not on macOS."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None  # 'security' not available (non-macOS)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def load_keys(config: Config) -> dict[str, str]:
    """Ensure each configured provider's key is in os.environ.

    Returns {provider: source} where source is one of 'env', 'keychain', 'missing'.
    """
    status: dict[str, str] = {}
    for provider in config.providers:
        env_name = PROVIDER_ENV.get(provider, provider.upper() + "_API_KEY")
        value = keychain_get(env_name)
        if value:
            os.environ[env_name] = value  # dedicated MARS key wins over ambient shell var
            status[provider] = "keychain"
        elif os.environ.get(env_name):
            status[provider] = "env"
        else:
            status[provider] = "missing"
    return status


def add_command(env_name: str) -> str:
    """The exact command a user runs to store a key (prompts, no shell history)."""
    return f"security add-generic-password -a {KEYCHAIN_ACCOUNT} -s {env_name} -w"
