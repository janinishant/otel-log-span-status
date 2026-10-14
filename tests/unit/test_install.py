import logging
import re

import pytest
from opentelemetry.trace import StatusCode

import otel_log_span_status
from otel_log_span_status import ConfigError, IgnoreRule, SpanStatusHandler, install


@pytest.fixture
def logger(request):
    logger = logging.getLogger(f"test_install.{request.node.name}")
    yield logger
    logger.handlers.clear()


@pytest.fixture
def root_logger():
    root = logging.getLogger()
    before = list(root.handlers)
    yield root
    root.handlers[:] = before


def span_handlers(logger):
    return [h for h in logger.handlers if isinstance(h, SpanStatusHandler)]


def test_defaults_to_root_logger(root_logger):
    handler = install()
    assert handler in root_logger.handlers


def test_attaches_to_given_logger(logger, root_logger):
    handler = install(logger=logger)
    assert span_handlers(logger) == [handler]
    assert handler not in root_logger.handlers


def test_without_config_has_no_rules(logger):
    assert not install(logger=logger)._rules  # pylint: disable=protected-access


def test_loads_rules_from_config(logger, tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('ignore:\n  - message_regex: "^Retrying"\n', encoding="utf-8")

    handler = install(path, logger=logger)

    rules = handler._rules  # pylint: disable=protected-access
    assert rules == (IgnoreRule(message_regex=re.compile("^Retrying")),)


def test_second_install_replaces_first(logger, tmp_path):
    other = logging.StreamHandler()
    logger.addHandler(other)
    first = install(logger=logger)

    path = tmp_path / "config.yaml"
    path.write_text('ignore:\n  - logger: "urllib3.*"\n', encoding="utf-8")
    second = install(path, logger=logger)

    assert span_handlers(logger) == [second]
    assert first is not second
    assert other in logger.handlers


def test_missing_config_installs_with_no_rules(logger, tmp_path, caplog):
    path = tmp_path / "missing.yaml"
    with caplog.at_level(logging.WARNING, logger="otel_log_span_status"):
        handler = install(path, logger=logger)

    assert span_handlers(logger) == [handler]
    assert not handler._rules  # pylint: disable=protected-access
    assert f"Config {path} not found" in caplog.text


def test_malformed_config_keeps_existing_handler(logger, tmp_path):
    existing = install(logger=logger)
    path = tmp_path / "config.yaml"
    path.write_text("ignores: []\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        install(path, logger=logger)
    assert span_handlers(logger) == [existing]


def test_malformed_config_raises(logger, tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("ignores: []\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        install(path, logger=logger)
    assert not span_handlers(logger)


@pytest.mark.usefixtures("root_logger")
def test_error_from_child_logger_marks_span_end_to_end(tracer, exporter, tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('ignore:\n  - logger: "urllib3.*"\n', encoding="utf-8")
    install(path)

    with tracer.start_as_current_span("ignored"):
        logging.getLogger("urllib3.connectionpool").error("Retrying")
    with tracer.start_as_current_span("marked"):
        logging.getLogger("app.payments").error("Charge failed")

    statuses = {s.name: s.status.status_code for s in exporter.get_finished_spans()}
    assert statuses == {"ignored": StatusCode.UNSET, "marked": StatusCode.ERROR}


def test_public_api():
    assert set(otel_log_span_status.__all__) == {
        "ConfigError",
        "IgnoreRule",
        "SpanStatusHandler",
        "install",
        "load_rules",
    }
