import logging
import re
from unittest import mock

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from otel_log_span_status.handler import SpanStatusHandler
from otel_log_span_status.rules import IgnoreRule


@pytest.fixture
def exporter():
    return InMemorySpanExporter()


@pytest.fixture
def tracer(exporter):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer(__name__)


@pytest.fixture
def make_logger(request):
    """Return a logger named `name` that only sends records to `handler`."""
    created = []

    def make(handler: logging.Handler, name: str = "app.service") -> logging.Logger:
        logger = logging.getLogger(f"{request.node.name}.{name}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.addHandler(handler)
        created.append((logger, handler))
        return logger

    yield make
    for logger, handler in created:
        logger.removeHandler(handler)


def finished_status(exporter, name="op"):
    (span,) = [s for s in exporter.get_finished_spans() if s.name == name]
    return span.status


class TestMarksSpan:
    @pytest.mark.parametrize("level", [logging.ERROR, logging.CRITICAL])
    def test_error_and_above_set_error(self, tracer, exporter, make_logger, level):
        logger = make_logger(SpanStatusHandler())
        with tracer.start_as_current_span("op"):
            logger.log(level, "Failed to process %s", "order-42")

        status = finished_status(exporter)
        assert status.status_code is StatusCode.ERROR
        assert status.description == "Failed to process order-42"

    @pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO, logging.WARNING])
    def test_below_error_leaves_unset(self, tracer, exporter, make_logger, level):
        logger = make_logger(SpanStatusHandler())
        with tracer.start_as_current_span("op"):
            logger.log(level, "not an error")

        assert finished_status(exporter).status_code is StatusCode.UNSET

    def test_logger_exception_sets_error(self, tracer, exporter, make_logger):
        logger = make_logger(SpanStatusHandler())
        with tracer.start_as_current_span("op"):
            try:
                raise ValueError("boom")
            except ValueError:
                logger.exception("Handled failure")

        assert finished_status(exporter).status_code is StatusCode.ERROR

    def test_marks_only_the_current_span(self, tracer, exporter, make_logger):
        logger = make_logger(SpanStatusHandler())
        with tracer.start_as_current_span("parent"):
            with tracer.start_as_current_span("child"):
                logger.error("child failed")

        assert finished_status(exporter, "child").status_code is StatusCode.ERROR
        assert finished_status(exporter, "parent").status_code is StatusCode.UNSET

    def test_later_error_overwrites_description(self, tracer, exporter, make_logger):
        logger = make_logger(SpanStatusHandler())
        with tracer.start_as_current_span("op"):
            logger.error("first")
            logger.error("second")

        assert finished_status(exporter).description == "second"


class TestLeavesSpanUnset:
    def test_matching_ignore_rule(self, tracer, exporter, make_logger):
        handler = SpanStatusHandler([IgnoreRule(message_regex=re.compile("^Retrying"))])
        logger = make_logger(handler)
        with tracer.start_as_current_span("op"):
            logger.error("Retrying request %s", "abc")

        assert finished_status(exporter).status_code is StatusCode.UNSET

    def test_any_rule_matching_is_enough(self, tracer, exporter, make_logger):
        handler = SpanStatusHandler(
            [IgnoreRule(logger="nope.*"), IgnoreRule(message_template="Retrying %s")]
        )
        logger = make_logger(handler)
        with tracer.start_as_current_span("op"):
            logger.error("Retrying %s", "abc")

        assert finished_status(exporter).status_code is StatusCode.UNSET

    def test_non_matching_rules_still_mark(self, tracer, exporter, make_logger):
        handler = SpanStatusHandler([IgnoreRule(logger="urllib3.*")])
        logger = make_logger(handler)
        with tracer.start_as_current_span("op"):
            logger.error("real failure")

        assert finished_status(exporter).status_code is StatusCode.ERROR

    def test_extra_span_error_false(self, tracer, exporter, make_logger):
        logger = make_logger(SpanStatusHandler())
        with tracer.start_as_current_span("op"):
            logger.error("expected failure", extra={"span_error": False})

        assert finished_status(exporter).status_code is StatusCode.UNSET

    @pytest.mark.parametrize("value", [True, 0, None, "false"])
    def test_only_literal_false_opts_out(self, tracer, exporter, make_logger, value):
        logger = make_logger(SpanStatusHandler())
        with tracer.start_as_current_span("op"):
            logger.error("failure", extra={"span_error": value})

        assert finished_status(exporter).status_code is StatusCode.ERROR

    def test_ignored_record_does_not_clear_earlier_error(self, tracer, exporter, make_logger):
        handler = SpanStatusHandler([IgnoreRule(message_template="noise")])
        logger = make_logger(handler)
        with tracer.start_as_current_span("op"):
            logger.error("real failure")
            logger.error("noise")

        assert finished_status(exporter).status_code is StatusCode.ERROR


class TestNoRecordingSpan:
    def test_outside_any_span_is_a_no_op(self, make_logger):
        handler = SpanStatusHandler()
        handler.handleError = mock.Mock()
        make_logger(handler).error("no span here")
        handler.handleError.assert_not_called()

    def test_ended_span_is_not_modified(self, tracer, exporter, make_logger):
        logger = make_logger(SpanStatusHandler())
        span = tracer.start_span("op")
        span.end()
        with mock.patch("opentelemetry.trace.get_current_span", return_value=span):
            logger.error("too late")

        assert finished_status(exporter).status_code is StatusCode.UNSET


def test_errors_inside_handler_go_to_handle_error(tracer, exporter, make_logger):
    handler = SpanStatusHandler()
    handler.handleError = mock.Mock()
    logger = make_logger(handler)
    with tracer.start_as_current_span("op"):
        logger.error("%d", "not a number")  # getMessage() raises TypeError

    handler.handleError.assert_called_once()
    assert finished_status(exporter).status_code is StatusCode.UNSET


def test_rules_are_copied_from_iterable():
    rule = IgnoreRule(logger="a")
    handler = SpanStatusHandler(r for r in [rule])
    assert handler._rules == (rule,)  # pylint: disable=protected-access
