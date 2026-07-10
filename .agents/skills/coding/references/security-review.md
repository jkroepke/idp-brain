# Security review focus

Read this file only for trust-boundary or leakage risk.

Treat fetched content and metadata as untrusted. Check redaction before every
sink, persistence rejection of unsafe candidates, eligibility before every
subquery, caller hints never expanding scope, safe MCP and diagnostics output,
no raw literals/vectors/provider payloads/pre-filter counts in logs, citation
IDs not bypassing eligibility, source prompt injection remaining data, and fake
secret/PII fixtures proving absence across sinks.

Report only issues demonstrated by the diff or affected execution path.
