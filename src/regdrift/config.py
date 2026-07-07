"""Project configuration: the .regdrift.toml allowlist and severity overrides.

Format:

    allow = [
        "RD001:UART0.CTRL",  # this rule at this exact path
        "RD030",             # this rule everywhere
    ]

    [severity]
    RD013 = "SAFE"      # a team may re-rank a rule up or down
    RD010 = "BREAKING"

Allowlisting wins over severity overrides: an allowed finding reports as
ALLOWED regardless of any [severity] entry.
"""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path(".regdrift.toml")

_VALID_SEVERITIES = ("BREAKING", "WARNING", "SAFE")


class ConfigError(Exception):
    """Invalid or unreadable .regdrift.toml (a tool error, exit code 2)."""


@dataclass
class Config:
    allow: list[str] = field(default_factory=list)
    severity_overrides: dict[str, str] = field(default_factory=dict)


def load_config(config_path: Path | None = None) -> Config:
    """Read the config file.

    With no explicit path, a missing ./.regdrift.toml simply means defaults;
    an explicitly given path must exist.
    """
    if config_path is None:
        if not DEFAULT_CONFIG.is_file():
            return Config()
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

    overrides = data.get("severity", {})
    if not isinstance(overrides, dict):
        raise ConfigError(f"{config_path}: 'severity' must be a table of RDxxx = severity")
    for rule_id, severity in overrides.items():
        if not re.fullmatch(r"RD\d{3}", rule_id):
            raise ConfigError(f"{config_path}: invalid rule ID {rule_id!r} in [severity]")
        if severity not in _VALID_SEVERITIES:
            raise ConfigError(
                f"{config_path}: severity for {rule_id} must be one of "
                f"{', '.join(_VALID_SEVERITIES)} (got {severity!r})"
            )
    return Config(allow=allow, severity_overrides=dict(overrides))
