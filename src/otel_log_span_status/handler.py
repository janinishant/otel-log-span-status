"""Logging handler that marks the active span as ERROR on error-level logs."""

import logging
from collections.abc import Iterable

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from otel_log_span_status.rules import IgnoreRule


class SpanStatusHandler(logging.Handler):
    """Sets the current span's status to ERROR for records at or above ERROR level.

    A record leaves the span untouched if it matches any ignore rule, if it was
    logged with ``extra={"span_error": False}``, or if there is no recording span.
    """

    def __init__(self, rules: Iterable[IgnoreRule] = ()) -> None:
        super().__init__(level=logging.ERROR)
        self._rules = tuple(rules)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if getattr(record, "span_error", True) is False:
                return

            span = trace.get_current_span()
            if not span.is_recording():
                return

            if any(rule.matches(record) for rule in self._rules):
                return

            span.set_status(Status(StatusCode.ERROR, record.getMessage()))
        except Exception:  # pylint: disable=broad-exception-caught
            # Never let span bookkeeping break the caller's logging.
            self.handleError(record)
