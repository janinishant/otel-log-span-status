import logging
import re

import pytest

from otel_log_span_status.rules import IgnoreRule


def make_record(
    name: str = "app.service",
    msg: str = "Failed to process %s",
    args: tuple = ("order-42",),
) -> logging.LogRecord:
    return logging.LogRecord(name, logging.ERROR, "app.py", 1, msg, args, None)


class TestLogger:
    def test_exact_name(self):
        assert IgnoreRule(logger="app.service").matches(make_record())

    def test_glob_matches_child(self):
        assert IgnoreRule(logger="app.*").matches(make_record(name="app.service.db"))

    def test_glob_does_not_match_bare_parent(self):
        assert not IgnoreRule(logger="app.*").matches(make_record(name="app"))

    def test_case_sensitive(self):
        assert not IgnoreRule(logger="App.*").matches(make_record())

    def test_no_match(self):
        assert not IgnoreRule(logger="urllib3.*").matches(make_record())


class TestMessageTemplate:
    def test_matches_unformatted_template(self):
        assert IgnoreRule(message_template="Failed to process %s").matches(make_record())

    def test_does_not_match_formatted_message(self):
        assert not IgnoreRule(message_template="Failed to process order-42").matches(make_record())


class TestMessageRegex:
    def test_searches_formatted_message(self):
        assert IgnoreRule(message_regex=re.compile(r"order-\d+")).matches(make_record())

    def test_search_not_fullmatch(self):
        assert IgnoreRule(message_regex=re.compile("process")).matches(make_record())

    def test_no_match(self):
        assert not IgnoreRule(message_regex=re.compile("^Timeout")).matches(make_record())


class TestCombinedFields:
    def test_all_fields_match(self):
        rule = IgnoreRule(
            logger="app.*",
            message_template="Failed to process %s",
            message_regex=re.compile("order"),
        )
        assert rule.matches(make_record())

    @pytest.mark.parametrize(
        "override",
        [
            {"logger": "other.*"},
            {"message_template": "Something else"},
            {"message_regex": re.compile("nope")},
        ],
    )
    def test_any_field_mismatch_fails(self, override):
        fields = dict(
            logger="app.*",
            message_template="Failed to process %s",
            message_regex=re.compile("order"),
        )
        fields.update(override)
        assert not IgnoreRule(**fields).matches(make_record())


def test_regex_not_evaluated_when_cheaper_check_fails():
    record = make_record(name="other")
    record.getMessage = lambda: pytest.fail("message should not be formatted")
    assert not IgnoreRule(logger="app.*", message_regex=re.compile("x")).matches(record)
