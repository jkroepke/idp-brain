from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.extractors import (
    ArtifactExtractionContext,
    ExtractorRegistry,
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
from idp_brain.ingestion.redaction_stage import RedactionStage
from idp_brain.models import Base
from idp_brain.repositories import ArtifactExtractionRepository

FIXTURES = Path("tests/fixtures/extractors")


def test_registry_selects_configured_basic_extractors() -> None:
    registry = ExtractorRegistry()

    assert isinstance(
        registry.select(_artifact("doc.md", "documentation")), MarkdownExtractor
    )
    assert isinstance(
        registry.select(_artifact("page.html", "documentation")), HtmlExtractor
    )
    assert isinstance(registry.select(_artifact("data.json", "example")), JsonExtractor)
    assert isinstance(
        registry.select(_artifact("config.yaml", "example")), YamlExtractor
    )
    assert isinstance(
        registry.select(_artifact("settings.toml", "example")), TomlExtractor
    )
    assert isinstance(registry.select(_artifact("plain.txt", "unknown")), TextExtractor)
    assert isinstance(
        registry.select(_artifact("sample.py", "source_code", language="python")),
        SourceCodeExtractor,
    )
    assert isinstance(
        registry.select(_artifact("openapi.yaml", "openapi_spec")),
        OpenApiExtractor,
    )
    assert isinstance(
        registry.select(_artifact("schema.json", "json_schema")),
        JsonSchemaExtractor,
    )


def test_registry_honors_profile_enabled_state_and_enabled_tools() -> None:
    markdown_profile = _profile(
        profile_id="fixture_profile",
        family="docs",
        enabled=True,
        tools=[{"tool_id": "builtin-markdown-html", "enabled": True}],
    )
    disabled_tool_profile = _profile(
        profile_id="fixture_profile",
        family="docs",
        enabled=True,
        tools=[{"tool_id": "builtin-markdown-html", "enabled": False}],
    )
    disabled_profile = _profile(
        profile_id="fixture_profile",
        family="docs",
        enabled=False,
        tools=[{"tool_id": "builtin-markdown-html", "enabled": True}],
    )

    assert isinstance(
        ExtractorRegistry(profiles=[markdown_profile]).select(
            _artifact("doc.md", "documentation")
        ),
        MarkdownExtractor,
    )
    for profile in (disabled_tool_profile, disabled_profile):
        try:
            ExtractorRegistry(profiles=[profile]).select(
                _artifact("doc.md", "documentation")
            )
        except LookupError as exc:
            assert "no enabled extractor tool" in str(exc)
        else:
            raise AssertionError(
                "disabled profile/tool unexpectedly selected extractor"
            )


def test_registry_uses_enabled_configured_fallback_profile() -> None:
    disabled_primary = _profile(
        profile_id="fixture_profile",
        family="docs",
        enabled=False,
        tools=[{"tool_id": "builtin-markdown-html", "enabled": True}],
        fallback_profile="fallback_text",
    )
    fallback = _profile(
        profile_id="fallback_text",
        family="docs",
        enabled=True,
        tools=[{"tool_id": "builtin-text", "enabled": True}],
    )

    assert isinstance(
        ExtractorRegistry(profiles=[disabled_primary, fallback]).select(
            _artifact("notes.unknown", "unknown")
        ),
        TextExtractor,
    )


def test_basic_extractors_emit_provenance_rich_candidates() -> None:
    cases = [
        (
            "doc.md",
            "documentation",
            None,
            {"heading", "section", "table", "code_block"},
        ),
        (
            "page.html",
            "documentation",
            None,
            {"heading", "section", "table", "code_block"},
        ),
        ("data.json", "example", None, {"object", "scalar"}),
        ("config.yaml", "example", None, {"object", "array", "scalar"}),
        ("settings.toml", "example", None, {"object", "scalar"}),
        ("plain.txt", "unknown", None, {"paragraph"}),
        ("openapi.yaml", "openapi_spec", None, {"endpoint", "schema", "scalar"}),
        ("schema.json", "json_schema", None, {"schema_path", "scalar"}),
        ("sample.py", "source_code", "python", {"symbol", "import"}),
    ]
    registry = ExtractorRegistry()

    for filename, role, language, expected_types in cases:
        artifact = _artifact(filename, role, language=language)
        result = registry.select(artifact).extract(
            artifact, (FIXTURES / filename).read_bytes()
        )
        candidate_types = {candidate.candidate_type for candidate in result.candidates}

        assert result.status == "completed", filename
        assert expected_types <= candidate_types, filename
        assert all(
            candidate.locator.startswith("fixture:") for candidate in result.candidates
        )
        assert all(candidate.metadata is not None for candidate in result.candidates)
        assert all(
            candidate.source_id == artifact.source_id for candidate in result.candidates
        )
        assert all(
            candidate.source_version_id == artifact.source_version_id
            for candidate in result.candidates
        )
        assert all(
            candidate.artifact_id == artifact.artifact_id
            for candidate in result.candidates
        )
        assert all(
            candidate.visibility_label == artifact.visibility_label
            for candidate in result.candidates
        )
        assert all(
            candidate.sensitivity_class == artifact.sensitivity_class
            for candidate in result.candidates
        )
        assert all(
            candidate.license_policy_label == artifact.license_policy_label
            for candidate in result.candidates
        )
        assert all(
            candidate.corpus_eligibility_label == artifact.corpus_eligibility_label
            for candidate in result.candidates
        )
        assert result.artifact.corpus_eligibility_label == "review_required"
        assert result.artifact.visibility_label == "invited_users"


def test_source_code_extractor_reports_symbols_and_unsupported_languages() -> None:
    extractor = SourceCodeExtractor()
    python_artifact = _artifact("sample.py", "source_code", language="python")
    python_result = extractor.extract(
        python_artifact, (FIXTURES / "sample.py").read_bytes()
    )

    symbols = {
        ".".join(candidate.symbol_path): candidate
        for candidate in python_result.candidates
        if candidate.candidate_type == "symbol"
    }
    assert set(symbols) == {"Widget", "Widget.render", "build_widget"}
    assert symbols["Widget"].signature_text == "class Widget"
    assert symbols["Widget.render"].symbol_path == ("Widget", "render")
    assert symbols["Widget.render"].line_range is not None
    assert "pathlib" in symbols["Widget.render"].metadata["imports"]
    assert symbols["Widget.render"].metadata["parser"] == "tree-sitter"

    unsupported = extractor.extract(
        _artifact("main.go", "source_code", language="go"),
        b"package main\nfunc main() {}\n",
    )
    assert unsupported.status == "skipped"
    assert unsupported.diagnostics[0].code == "unsupported_language"


def test_malformed_input_diagnostics_are_sanitized() -> None:
    artifact = _artifact("bad.json", "example")
    result = JsonExtractor().extract(artifact, b'{"password": "hunter2",}')

    assert result.status == "failed"
    diagnostic = result.diagnostics[0].to_dict()
    assert "hunter2" not in str(diagnostic)
    assert "password" not in str(diagnostic).lower()


def test_safe_extraction_record_persists_no_raw_candidate_text() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(engine)
        artifact = _artifact("doc.md", "documentation")
        result = MarkdownExtractor().extract(
            artifact, (FIXTURES / "doc.md").read_bytes()
        )

        with Session(engine) as session:
            sanitized = RedactionStage().redact(result)
            row = ArtifactExtractionRepository(session).create_from_sanitized_result(
                sanitized,
                ingestion_run_id="run:fixture",
            )
            session.commit()

            assert row.status == "completed"
            assert row.diagnostics["candidate_count"] == len(result.candidates)
            persisted = str(row.diagnostics)
            assert "Intro paragraph" not in persisted
            assert 'print("hello")' not in persisted
    finally:
        engine.dispose()


def _artifact(
    path: str,
    role: str,
    *,
    language: str | None = None,
) -> ArtifactExtractionContext:
    return ArtifactExtractionContext(
        artifact_id=f"artifact:{path}",
        source_id="source:fixture",
        source_version_id="source-version:fixture",
        path=path,
        logical_locator=f"fixture:{path}",
        source_type="local_directory",
        artifact_role=role,
        language=language,
        extractor_profile="fixture_profile",
        visibility_label="invited_users",
        sensitivity_class="internal",
        license_policy_label="review_required",
        corpus_eligibility_label="review_required",
    )


def _profile(**overrides: object) -> ExtractorProfileConfig:
    payload = {
        "profile_id": "fixture_profile",
        "family": "docs",
        "enabled": True,
        "file_patterns": ["**/*"],
        "include_generated": False,
        "include_vendored": False,
        "tools": [],
        "validator_commands": [],
        "fallback_profile": None,
    }
    payload.update(overrides)
    return ExtractorProfileConfig.model_validate(payload)
