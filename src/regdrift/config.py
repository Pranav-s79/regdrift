"""Project configuration: the .regdrift.toml allowlist.

Format:

    allow = [
        "RD001:UART0.CTRL",  # this rule at this exact path
        "RD030",             # this rule everywhere
    ]
"""

import tomllib
from pathlib import Path

DEFAULT_CONFIG = Path(".regdrift.toml")


class ConfigError(Exception):
    """Invalid or unreadable .regdrift.toml (a tool error, exit code 2)."""


def load_allowlist(config_path: Path | None = None) -> list[str]:
    """Read allow entries from a config file.

    With no explicit path, a missing ./.regdrift.toml simply means an empty
    allowlist; an explicitly given path must exist.
    """
    if config_path is None:
        if not DEFAULT_CONFIG.is_file():
            return []
        config_path = DEFAULT_CONFIG
    try:
        with open(config_path, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise ConfigError(f"cannot read {config_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {config_path}: {exc}") from exc
    allow = data.get("allow", [])
    if not isinstance(allow, list) or not all(isinstance(entry, str) for entry in allow):
        raise ConfigError(f"{config_path}: 'allow' must be a list of strings")
    return allow
