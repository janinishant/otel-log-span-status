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

    With no `config_path` there are no ignore rules, so every error log marks the span.
    If `config_path` is given, the file must exist and be valid; otherwise this raises
    FileNotFoundError or ConfigError and leaves any existing handler in place.

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
