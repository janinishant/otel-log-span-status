# otel-log-span-status

[![Lint](https://github.com/janinishant/otel-log-span-status/actions/workflows/lint.yml/badge.svg)](https://github.com/janinishant/otel-log-span-status/actions/workflows/lint.yml)
[![Test](https://github.com/janinishant/otel-log-span-status/actions/workflows/test.yml/badge.svg)](https://github.com/janinishant/otel-log-span-status/actions/workflows/test.yml)

Marks the active OpenTelemetry span as `ERROR` whenever an error-level log is emitted.
Patterns listed in a YAML config are exempt, so expected or handled errors don't mark the span.

> Status: early development.

## Why This Exists

In OpenTelemetry, tail samplers rely on `StatusCode.ERROR` to decide which traces to keep. In real-world Python services, however, engineers rarely mutate span statuses manually—they catch exceptions, call `logger.error()`, and return a fallback response.

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
(Dropped by Tail Sampler 💰)             (Kept by Tail Sampler 🔍)
```

| Approach | Captures Caught Errors? | Blocks Noisy 3rd-Party Errors? | Tail-Sampling Cost |
|---|---|---|---|
| Standard OpenTelemetry | No (only unhandled exceptions) | N/A | Low (but misses real bugs) |
| Naïve Logging Hook | Yes | No | Very High (false positives) |
| **otel-log-span-status** | **Yes** | **Yes (via per-service YAML)** | **Optimal (true errors only)** |
