"""Shared path-aware structured document extraction helpers."""

from __future__ import annotations

from collections.abc import Iterator

from idp_brain.ingestion.extractors.base import ExtractionCandidate


def iter_structured_candidates(
    value: object,
    *,
    locator_prefix: str,
    path: tuple[str, ...] = (),
) -> Iterator[ExtractionCandidate]:
    """Yield path-aware object, array, and scalar candidates."""

    locator = _locator(locator_prefix, path)
    if isinstance(value, dict):
        yield ExtractionCandidate(
            candidate_type="object",
            text=None,
            locator=locator,
            key_path=path,
        )
        for key in sorted(value):
            yield from iter_structured_candidates(
                value[key],
                locator_prefix=locator_prefix,
                path=(*path, str(key)),
            )
        return
    if isinstance(value, list):
        yield ExtractionCandidate(
            candidate_type="array",
            text=None,
            locator=locator,
            key_path=path,
            metadata={"length": len(value)},
        )
        for index, item in enumerate(value):
            yield from iter_structured_candidates(
                item,
                locator_prefix=locator_prefix,
                path=(*path, str(index)),
            )
        return
    yield ExtractionCandidate(
        candidate_type="scalar",
        text=_scalar_text(value),
        locator=locator,
        key_path=path,
        metadata={"value_type": type(value).__name__},
    )


def _locator(prefix: str, path: tuple[str, ...]) -> str:
    if not path:
        return prefix
    return (
        prefix
        + "#/"
        + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)
    )


def _scalar_text(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
