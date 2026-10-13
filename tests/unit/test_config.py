import re
from pathlib import Path

import pytest

from otel_log_span_status.config import ConfigError, load_rules
from otel_log_span_status.rules import IgnoreRule


@pytest.fixture
def write_config(tmp_path: Path):
    def write(content: str) -> Path:
        path = tmp_path / "config.yaml"
        path.write_text(content, encoding="utf-8")
        return path

    return write


class TestValidConfig:
    def test_all_rule_fields(self, write_config):
        path = write_config(
            """
ignore:
  - logger: "urllib3.*"
  - message_template: "Retrying request %s"
  - logger: "payments.*"
    message_regex: "card declined"
"""
        )
        assert load_rules(path) == (
            IgnoreRule(logger="urllib3.*"),
            IgnoreRule(message_template="Retrying request %s"),
            IgnoreRule(logger="payments.*", message_regex=re.compile("card declined")),
        )

    def test_regex_is_compiled(self, write_config):
        (rule,) = load_rules(write_config('ignore:\n  - message_regex: "^Cache miss"\n'))
        assert isinstance(rule.message_regex, re.Pattern)

    def test_accepts_str_path(self, write_config):
        path = write_config('ignore:\n  - logger: "a"\n')
        assert load_rules(str(path)) == (IgnoreRule(logger="a"),)

    @pytest.mark.parametrize("content", ["", "# only a comment\n", "ignore:\n", "ignore: []\n"])
    def test_empty_means_no_rules(self, write_config, content):
        # Compare to () rather than `not ...` so None or [] would fail the test.
        assert load_rules(write_config(content)) == ()  # pylint: disable=use-implicit-booleaness-not-comparison


class TestInvalidConfig:
    @pytest.mark.parametrize(
        ("content", "error"),
        [
            ("ignore: [\n", "invalid YAML"),
            ("- logger: a\n", "top level must be a mapping"),
            ("ignores: []\n", "unknown top-level keys: ['ignores']"),
            ("ignore:\n  logger: a\n", "'ignore' must be a list"),
            ("ignore:\n  - urllib3\n", "ignore[0]: rule must be a mapping"),
            ("ignore:\n  - {}\n", "ignore[0]: rule must set at least one of"),
            ("ignore:\n  - logger: a\n  - loger: b\n", "ignore[1]: unknown keys ['loger']"),
            ("ignore:\n  - logger: 42\n", "ignore[0].logger: must be a non-empty string"),
            ('ignore:\n  - logger: ""\n', "ignore[0].logger: must be a non-empty string"),
            ("ignore:\n  - logger:\n", "ignore[0].logger: must be a non-empty string"),
            ('ignore:\n  - message_regex: "("\n', "ignore[0].message_regex: invalid regex"),
        ],
    )
    def test_raises_config_error(self, write_config, content, error):
        path = write_config(content)
        with pytest.raises(ConfigError, match=re.escape(error)) as exc_info:
            load_rules(path)
        assert str(path) in str(exc_info.value)

    def test_config_error_is_value_error(self):
        assert issubclass(ConfigError, ValueError)

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_rules(tmp_path / "missing.yaml")
