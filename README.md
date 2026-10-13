# otel-log-span-status

Marks the active OpenTelemetry span as `ERROR` whenever an error-level log is emitted.
Patterns listed in a YAML config are exempt, so expected or handled errors don't mark the span.

> Status: early development.
