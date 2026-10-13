"""Ignore rules: decide whether an error-level log record should NOT mark the span as ERROR."""

import fnmatch
import logging
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IgnoreRule:
    """A single ignore rule.

    Every field that is set must match (AND). A rule with no fields set is invalid.
    Multiple rules are combined with OR by the caller.
    """

    logger: str | None = None  # glob against record.name, e.g. "urllib3.*"
    message_template: str | None = None  # exact match against record.msg (unformatted)
    message_regex: re.Pattern[str] | None = None  # re.search against the formatted message

    def matches(self, record: logging.LogRecord) -> bool:
        """Return True if every field set on this rule matches the record."""
        # Cheapest checks first; message formatting is deferred until needed.
        if self.logger is not None and not fnmatch.fnmatchcase(record.name, self.logger):
            return False

        if self.message_template is not None and record.msg != self.message_template:
            return False

        if self.message_regex is not None and not self.message_regex.search(record.getMessage()):
            return False

        return True
