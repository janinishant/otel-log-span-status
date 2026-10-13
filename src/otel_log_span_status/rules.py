"""Ignore rules: decide whether an error-level log record should NOT mark the span as ERROR."""

from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass
from typing import Optional, Pattern


@dataclass(frozen=True)
class IgnoreRule:
    """A single ignore rule.

    Every field that is set must match (AND). A rule with no fields set is invalid.
    Multiple rules are combined with OR by the caller.
    """

    logger: Optional[str] = None  # glob against record.name, e.g. "urllib3.*"
    message_template: Optional[str] = None  # exact match against record.msg (unformatted)
    message_regex: Optional[Pattern[str]] = None  # re.search against the formatted message
    exception_type: Optional[str] = None  # fully qualified name, e.g. "redis.exceptions.TimeoutError"

    def matches(self, record: logging.LogRecord) -> bool:
        # Cheapest checks first; message formatting is deferred until needed.
        if self.logger is not None and not fnmatch.fnmatchcase(record.name, self.logger):
            return False

        if self.message_template is not None and record.msg != self.message_template:
            return False

        if self.exception_type is not None:
            exc_type = record.exc_info[0] if record.exc_info else None
            if exc_type is None or not _is_subclass_by_name(exc_type, self.exception_type):
                return False

        if self.message_regex is not None and not self.message_regex.search(record.getMessage()):
            return False

        return True


def _is_subclass_by_name(exc_type: type, qualified_name: str) -> bool:
    """True if exc_type or any of its bases has the given fully qualified name.

    Matching by name avoids importing the exception's module at config-load time.
    """
    for cls in exc_type.__mro__:
        if f"{cls.__module__}.{cls.__qualname__}" == qualified_name:
            return True
        # Allow bare names for builtins: "TimeoutError" instead of "builtins.TimeoutError".
        if cls.__module__ == "builtins" and cls.__qualname__ == qualified_name:
            return True
    return False
