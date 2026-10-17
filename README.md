# otel-log-span-status

[![PyPI](https://img.shields.io/pypi/v/otel-log-span-status)](https://pypi.org/project/otel-log-span-status/)
[![Lint](https://github.com/janinishant/otel-log-span-status/actions/workflows/lint.yml/badge.svg)](https://github.com/janinishant/otel-log-span-status/actions/workflows/lint.yml)
[![Test](https://github.com/janinishant/otel-log-span-status/actions/workflows/test.yml/badge.svg)](https://github.com/janinishant/otel-log-span-status/actions/workflows/test.yml)

Marks the active OpenTelemetry span as `ERROR` when you log an error, so tail sampling keeps the trace.
Logs you list in a YAML file are ignored, so expected or noisy errors don't.

In Python it's common to catch an exception, log it and return a response. The span still ends without an error status. If your tail sampler keeps traces that contain an `ERROR` span, it drops this one, and the trace you need to debug the failure is gone.

> Version 0.1. The API may change before 1.0.

![Animated walkthrough: why tail samplers drop traces whose errors only reach the logs, installing otel-log-span-status, a four-line setup that marks the active span as ERROR, and YAML ignore rules that keep expected errors from doing the same](https://raw.githubusercontent.com/janinishant/otel-log-span-status/main/docs/demo.gif)

## Install

```sh
pip install otel-log-span-status
```

Requires Python 3.10+ and `opentelemetry-api` 1.20+. You also need an OpenTelemetry SDK configured in your service; this library only sets span status.

## Before and after

```python
import logging

from opentelemetry import trace

logger = logging.getLogger("checkout")
tracer = trace.get_tracer(__name__)


def charge(order):
    with tracer.start_as_current_span("charge"):
        try:
            gateway.charge(order)
        except GatewayTimeout:
            logger.exception("charge failed for order %s", order.id)
            return Response(status=502)
```

**Before:** the error is in your logs, but the `charge` span ends with status `UNSET`. To the sampler, it's a healthy trace.

**After:** add one call at startup and the same code marks the span `ERROR`:

```python
import otel_log_span_status

otel_log_span_status.install("otel-log-span-status.yaml")
```

## Ignoring noise

Marking every error log isn't right either. A retry that eventually succeeds, or a chatty library, would make you keep traces nobody needs. List those logs in the config file:

```yaml
# otel-log-span-status.yaml
ignore:
  - logger: "urllib3.*"                      # logger name glob
  - message_template: "Retrying request %s"  # exact match on the unformatted message
  - logger: "payments.*"                     # fields within one rule must all match
    message_regex: "card declined"
```

How rules match:

- A log is ignored if **any** rule matches it. Within one rule, **every** field you set must match.
- `logger` is a glob on the logger name, such as `urllib3.*`. It is case-sensitive.
- `message_template` must equal the message **before** formatting: the `"Retrying request %s"` in `logger.error("Retrying request %s", url)`. An f-string such as `logger.error(f"Retrying request {url}")` has no template, so it can never match. Use `message_regex` for those.
- `message_regex` is searched (`re.search`) in the formatted message.

To skip a single call without a rule, pass `extra={"span_error": False}`.

## The other half: keep error traces in the Collector

This library sets the span status. Your tail sampler decides what to keep. For example, with the OpenTelemetry Collector's [`tail_sampling` processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/tailsamplingprocessor) (in the contrib distribution):

```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: keep-errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: keep-slow
        type: latency
        latency: { threshold_ms: 2000 }
      - name: sample-the-rest
        type: probabilistic
        probabilistic: { sampling_percentage: 5 }
```

A trace is kept if any policy matches, so errors are always kept and the rest is sampled.

## Details

- **Which logs:** `ERROR` and above, including `CRITICAL` and `logger.exception(...)`.
- **Where it attaches:** `install()` adds a handler to the root logger, so it sees every logger that propagates to root. Loggers with `propagate = False` are not seen. To attach somewhere else, pass `install(path, logger=some_logger)`.
- **No span:** if there is no recording span, nothing happens.
- **Config errors:** the config file is optional. With no path, every error log marks the span. If you pass a path, the file must exist and be valid, or `install()` raises `FileNotFoundError` or `ConfigError`.
- **Reloading:** calling `install()` again replaces the handler it installed before, so you can use it to reload the config.
- **Safety:** an error inside the handler is reported through `logging`'s usual `handleError` and never breaks your logging call.

## How this differs from existing OpenTelemetry logging integrations

- [`opentelemetry-instrumentation-logging`](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation/opentelemetry-instrumentation-logging) adds trace and span IDs to log records so you can find a log's trace. It does not change span status.
- The SDK's `LoggingHandler` exports log records as OpenTelemetry logs. It does not change span status either.

Use either alongside this library.

## Why this exists

I wrote about the problem in more detail in [Error Logs and Missing Traces](https://www.nishantjani.com/blog/error-logs-missing-traces/).

## License

Apache-2.0. See [LICENSE](https://github.com/janinishant/otel-log-span-status/blob/main/LICENSE).
