# otel-log-span-status

[![Lint](https://github.com/janinishant/otel-log-span-status/actions/workflows/lint.yml/badge.svg)](https://github.com/janinishant/otel-log-span-status/actions/workflows/lint.yml)
[![Test](https://github.com/janinishant/otel-log-span-status/actions/workflows/test.yml/badge.svg)](https://github.com/janinishant/otel-log-span-status/actions/workflows/test.yml)

Marks the active OpenTelemetry span as `ERROR` whenever an error-level log is emitted.
Patterns listed in a YAML config are exempt, so expected or handled errors don't mark the span.

> Status: early development.

## Usage

```python
import otel_log_span_status

otel_log_span_status.install("otel-log-span-status.yaml")
```

```yaml
# otel-log-span-status.yaml
ignore:
  - logger: "urllib3.*"                      # logger name glob
  - message_template: "Retrying request %s"  # exact match on the unformatted message
  - logger: "payments.*"                     # fields within one rule must all match
    message_regex: "card declined"
```

The YAML is optional. If you call `install()` with no path, or the file doesn't exist, every error log marks the span; a missing file also logs a warning. `install()` attaches a handler to the root logger. Records from any logger that propagates to root are checked. To skip a single call without a config rule, pass `extra={"span_error": False}`.

## Why This Exists

In OpenTelemetry, tail samplers rely on `StatusCode.ERROR` to decide which traces to keep. In real-world Python services, however, mutating span statuses manually is painful.

This creates an expensive gap between your logs and your traces:

- **Default OTel (Blind Sampling):** Caught errors are logged, but the span status remains `UNSET`. Your tail sampler assumes the trace is healthy and drops it—destroying the exact traces you need during an outage.
- **Naïve Log-to-Span Hook (Cost Explosion):** Automatically setting the active span to `ERROR` on every `logger.error()` call poisons healthy traces. Third-party libraries (`urllib3`, `botocore`) and handled retries emit thousands of non-fatal error logs, forcing your tail sampler to store millions of false-positive traces.

**otel-log-span-status** sits inside the Python runtime and bridges `logging` with OpenTelemetry. It promotes `logger.error()` calls to `StatusCode.ERROR` on the active span, while evaluating a fast, service-specific YAML ignore list (by logger name, raw message template, or regex) so noisy false positives never trigger tail sampling.

```
logger.error("...")
        │
        ▼
┌────────────────────────────────────────────────────────┐
│  otel-log-span-status In-Process Handler               │
│                                                        │
│  Matches YAML Ignore Rules?                            │
│  (1. Logger Name ──► 2. Log Template ──► 3. Regex)     │
└───────┬────────────────────────────────────────┬───────┘
        │ YES (Noisy / Handled Retry)            │ NO (Real Error)
        ▼                                        ▼
Span Status: UNSET                       Span Status: ERROR
(Dropped by Tail Sampler)                (Kept by Tail Sampler)
```
