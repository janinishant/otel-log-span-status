"""Load ignore rules from a YAML config file.

Expected format:

    ignore:
      - logger: "urllib3.*"
      - message_template: "Retrying request %s"
      - logger: "payments.*"
        message_regex: "card declined"
"""

import os
import re
from typing import Any

import yaml

from otel_log_span_status.rules import IgnoreRule


class ConfigError(ValueError):
    """Raised when the config file is malformed."""


def load_rules(path: str | os.PathLike[str]) -> tuple[IgnoreRule, ...]:
    """Read ignore rules from a YAML file, failing fast on anything malformed."""
    with open(path, encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: invalid YAML: {e}") from e

    # An empty file means no rules.
    if data is None:
        return ()
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping, got {type(data).__name__}")

    unknown = data.keys() - {"ignore"}
    if unknown:
        raise ConfigError(f"{path}: unknown top-level keys: {sorted(unknown)}")

    entries = data.get("ignore") or []
    if not isinstance(entries, list):
        raise ConfigError(f"{path}: 'ignore' must be a list, got {type(entries).__name__}")

    return tuple(_parse_rule(entry, f"{path}: ignore[{i}]") for i, entry in enumerate(entries))


def _parse_rule(entry: Any, where: str) -> IgnoreRule:
    allowed = {"logger", "message_template", "message_regex"}

    if not isinstance(entry, dict):
        raise ConfigError(f"{where}: rule must be a mapping, got {type(entry).__name__}")
    if not entry:
        raise ConfigError(f"{where}: rule must set at least one of {sorted(allowed)}")

    unknown = entry.keys() - allowed
    if unknown:
        raise ConfigError(f"{where}: unknown keys {sorted(unknown)}; allowed: {sorted(allowed)}")

    for key, value in entry.items():
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{where}.{key}: must be a non-empty string")

    message_regex = None
    if "message_regex" in entry:
        try:
            message_regex = re.compile(entry["message_regex"])
        except re.error as e:
            raise ConfigError(f"{where}.message_regex: invalid regex: {e}") from e

    return IgnoreRule(
        logger=entry.get("logger"),
        message_template=entry.get("message_template"),
        message_regex=message_regex,
    )
