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

    The config is optional: with no `config_path`, or if the file doesn't exist, no
    ignore rules apply. A malformed file still raises ConfigError. Calling install()
    again replaces the previously installed handler, so it can be used to reload the
    config.
    """
    rules: tuple[IgnoreRule, ...] = ()
    if config_path is not None:
        try:
            rules = load_rules(config_path)
        except FileNotFoundError:
            logging.getLogger(__name__).warning(
                "Config %s not found; installing with no ignore rules", config_path
            )
    target = logger if logger is not None else logging.getLogger()

    for existing in [h for h in target.handlers if isinstance(h, SpanStatusHandler)]:
        target.removeHandler(existing)

    handler = SpanStatusHandler(rules)
    target.addHandler(handler)
    return handler
