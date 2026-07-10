# Codex adapter

This file is the Codex-facing repository adapter. Shared project facts and
working rules live in
[docs/agent-operating-model.md](docs/agent-operating-model.md); read it before
planning or changing code.

Use these authoritative sources as required:

- [README.md](README.md) for product behavior and usage.
- [RULES.md](RULES.md) for compatibility rule IDs and meanings.
- [CONTRIBUTING.md](CONTRIBUTING.md) and
  [pyproject.toml](pyproject.toml) for setup and validation.

Keep Codex-only configuration under `.codex/`. Do not modify Claude-specific
settings, skills, or agents unless the task explicitly requires cross-tool
alignment. Report missing evidence rather than guessing.
