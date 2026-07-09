from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from idp_brain.ingestion.extractors import (
    ArtifactExtractionContext,
    HtmlExtractor,
    JsonExtractor,
    JsonSchemaExtractor,
    MarkdownExtractor,
    OpenApiExtractor,
    SourceCodeExtractor,
    TextExtractor,
    TomlExtractor,
    YamlExtractor,
)

FIXTURES = Path("tests/fixtures/ingestion/extractors")


def test_basic_extractors_emit_policy_labeled_candidates(
    artifact_context_factory: Callable[..., ArtifactExtractionContext],
) -> None:
    cases = [
        (
            MarkdownExtractor(),
            Path("tests/fixtures/ingestion/local/guide.md"),
            "guide.md",
            "documentation",
            None,
        ),
        (HtmlExtractor(), FIXTURES / "page.html", "page.html", "documentation", None),
        (
            JsonExtractor(),
            Path("tests/fixtures/ingestion/local/data.json"),
            "data.json",
            "structured_data",
            None,
        ),
        (
            YamlExtractor(),
            FIXTURES / "config.yaml",
            "config.yaml",
            "structured_data",
            None,
        ),
        (
            TomlExtractor(),
            FIXTURES / "settings.toml",
            "settings.toml",
            "structured_data",
            None,
        ),
        (TextExtractor(), FIXTURES / "plain.txt", "plain.txt", "documentation", None),
        (
            OpenApiExtractor(),
            FIXTURES / "openapi.yaml",
            "openapi.yaml",
            "openapi_spec",
            None,
        ),
        (
            JsonSchemaExtractor(),
            FIXTURES / "schema.json",
            "schema.json",
            "json_schema",
            None,
        ),
        (
            SourceCodeExtractor(),
            FIXTURES / "sample.py",
            "sample.py",
            "source_code",
            "python",
        ),
    ]

    for extractor, fixture, path, role, language in cases:
        result = extractor.extract(
            artifact_context_factory(path, role, language=language),
            fixture.read_bytes(),
        )
        assert result.status == "completed"
        assert result.candidates
        assert all(
            candidate.source_id == "source:ingestion" for candidate in result.candidates
        )
        assert all(
            candidate.source_version_id == "source-version:ingestion"
            for candidate in result.candidates
        )
        assert all(
            candidate.visibility_label == "invited_users"
            for candidate in result.candidates
        )
        assert all(
            candidate.corpus_eligibility_label == "review_required"
            for candidate in result.candidates
        )
        assert all(
            candidate.license_policy_label == "review_required"
            for candidate in result.candidates
        )


def test_source_code_extractor_preserves_parent_symbol_context(
    artifact_context_factory: Callable[..., ArtifactExtractionContext],
) -> None:
    result = SourceCodeExtractor().extract(
        artifact_context_factory("sample.py", "source_code", language="python"),
        (FIXTURES / "sample.py").read_bytes(),
    )

    assert any(
        candidate.symbol_path == ("Widget", "render") for candidate in result.candidates
    )
