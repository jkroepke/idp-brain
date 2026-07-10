# Day-2 Operations

This phase adds the complete local OpenTelemetry backend stack, OpenTelemetry metrics, logs and traces, database backup and restore verification, and the final Python 3.14 free-threaded integration test.

All application telemetry uses OpenTelemetry APIs and OTLP. Prometheus acts only as the metrics backend through its native OTLP receiver.
