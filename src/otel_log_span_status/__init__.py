"""Mark the active OpenTelemetry span as ERROR on error-level logs, with a YAML ignore list."""

import logging
import os

from otel_log_span_status.config import ConfigError, load_rules
from otel_log_span_status.handler import SpanStatusHandler
from otel_log_span_status.rules import IgnoreRule

__all__ = ["ConfigError", "IgnoreRule", "SpanStatusHandler", "install", "load_rules"]


def install(
    config_path: str | os.PathLike[str] | None = None,
    logger: logging.Logger | None = None,
) -> SpanStatusHandler:
    """Attach a SpanStatusHandler to `logger` (the root logger by default).

    Rules are loaded from `config_path` if given; a missing or malformed file raises.
    Calling install() again replaces the previously installed handler, so it can be
    used to reload the config.
    """
    rules = load_rules(config_path) if config_path is not None else ()
    target = logger if logger is not None else logging.getLogger()

    for existing in [h for h in target.handlers if isinstance(h, SpanStatusHandler)]:
        target.removeHandler(existing)

    handler = SpanStatusHandler(rules)
    target.addHandler(handler)
    return handler
