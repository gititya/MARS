"""Load provider API keys from the macOS Keychain into the environment.

Keys are stored as generic passwords under account 'aditya', with scoped service
names like 'OpenAI:mars' and 'Anthropic:mars'. This keeps keys encrypted at rest
and scoped to MARS: nothing is exported globally and nothing is written to disk
in plaintext.

A scoped MARS Keychain entry takes precedence over an ambient shell variable, so
a dedicated MARS key always wins over a stale or shared global key. If no
Keychain entry exists, MARS falls back to the shell environment (useful on CI /
non-macOS).
"""

import os
import subprocess

from mars.config import Config

PROVIDER_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
PROVIDER_KEYCHAIN_SERVICE = {
    "anthropic": "Anthropic:mars",
    "openai": "OpenAI:mars",
    "gemini": "Gemini:mars",
}
KEYCHAIN_ACCOUNT = "aditya"


def keychain_service_for(provider: str) -> str:
    return PROVIDER_KEYCHAIN_SERVICE.get(provider, f"{provider.title()}:mars")


def keychain_service_for_env(env_name: str) -> str:
    for provider, provider_env in PROVIDER_ENV.items():
        if provider_env == env_name:
            return keychain_service_for(provider)
    return env_name


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
        value = keychain_get(keychain_service_for(provider))
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
    service = keychain_service_for_env(env_name)
    return f"security add-generic-password -a {KEYCHAIN_ACCOUNT} -s {service} -w"


def update_command(env_name: str) -> str:
    """Delete then re-add with a hidden prompt - keeps the key out of shell history."""
    service = keychain_service_for_env(env_name)
    return (
        f"security delete-generic-password -a {KEYCHAIN_ACCOUNT} -s {service} ; "
        f"security add-generic-password -a {KEYCHAIN_ACCOUNT} -s {service} -w"
    )
