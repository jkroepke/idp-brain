"""Conservative intent parsing for exact lookup retrieval."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_QUOTED_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_TOKEN_RE = re.compile(r"[A-Za-z0-9_./:{}/?-]+")
_VERSION_RE = re.compile(r"^(?:v|V)?\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9_.-]+)?$")
_ERROR_RE = re.compile(r"^(?:[A-Z][A-Z0-9_]{2,}|[A-Za-z]+(?:Error|Exception))$")


@dataclass(frozen=True)
class QueryIntent:
    """Field-specific exact lookup terms inferred from a query."""

    symbols: tuple[str, ...] = ()
    artifact_paths: tuple[str, ...] = ()
    endpoint_paths: tuple[str, ...] = ()
    schema_keys: tuple[str, ...] = ()
    version_strings: tuple[str, ...] = ()
    error_strings: tuple[str, ...] = ()
    quoted_strings: tuple[str, ...] = ()
    fuzzy_terms: tuple[str, ...] = ()

    def field_terms(self) -> dict[str, tuple[str, ...]]:
        """Return lookup fields mapped to deduplicated query terms."""

        heading_terms = self.quoted_strings + self.schema_keys
        text_terms = self.error_strings + self.quoted_strings
        return {
            "symbol_path": self.symbols,
            "artifact_path": self.artifact_paths,
            "structure_path": self.endpoint_paths + self.schema_keys,
            "heading_path": heading_terms,
            "signature_text": self.symbols + self.error_strings,
            "version_label": self.version_strings,
            "sanitized_text": text_terms,
        }


def parse_query_intent(query_text: str) -> QueryIntent:
    """Parse probable exact identifiers without product-specific rules."""

    quoted = _dedupe(
        match.group(1) or match.group(2) or ""
        for match in _QUOTED_RE.finditer(query_text)
    )
    tokens = _dedupe(
        match.group(0).strip(".,;()[]") for match in _TOKEN_RE.finditer(query_text)
    )

    symbols: list[str] = []
    paths: list[str] = []
    endpoints: list[str] = []
    schema_keys: list[str] = []
    versions: list[str] = []
    errors: list[str] = []
    fuzzy: list[str] = []

    for token in tokens:
        if not token:
            continue
        if _VERSION_RE.match(token):
            versions.append(token)
        if token.startswith("/") and len(token) > 1:
            endpoints.append(token)
        if "/" in token or re.search(
            r"\.(?:md|txt|ya?ml|json|toml|py|ts|js|html)$", token
        ):
            paths.append(token)
        if "::" in token or "." in token and token not in paths:
            symbols.append(token)
        if token.startswith("--") or "_" in token or token.startswith("$"):
            schema_keys.append(token.lstrip("-$"))
        if _ERROR_RE.match(token):
            errors.append(token)
        if len(token) >= 4 and token.isidentifier():
            fuzzy.append(token)

    return QueryIntent(
        symbols=_dedupe(symbols),
        artifact_paths=_dedupe(paths),
        endpoint_paths=_dedupe(endpoints),
        schema_keys=_dedupe(schema_keys),
        version_strings=_dedupe(versions),
        error_strings=_dedupe(errors),
        quoted_strings=quoted,
        fuzzy_terms=_dedupe(fuzzy),
    )


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for value in values:
        text = str(value).strip()
        if text:
            seen.setdefault(text, None)
    return tuple(seen)
