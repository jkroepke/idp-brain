from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from idp_brain.config import load_security_config
from idp_brain.ingestion.extractors import ArtifactExtractionContext, MarkdownExtractor
from idp_brain.ingestion.redaction_stage import RedactionStage, UnredactedCandidateError
from idp_brain.models import (
    Artifact,
    Base,
    IngestionRun,
    LicenseFinding,
    RedactionEvent,
    Source,
    SourceVersion,
)
from idp_brain.repositories import (
    ArtifactExtractionRepository,
    LicenseFindingRepository,
    RedactionEventRepository,
)

FIXTURE_PATH = Path("tests/fixtures/redaction/unsafe.md")
RAW_SECRETS = (
    "sk-test-secret",
    "eyJhbGciOiJIUzI1NiJ9.secret",
    "hunter2",
    "alice@example.test",
)


def test_redaction_stage_replaces_secret_and_pii_values_before_persistence() -> None:
    security = load_security_config(Path("config/security.yaml"))
    extraction = MarkdownExtractor().extract(
        _artifact(sensitivity_class="confidential"),
        FIXTURE_PATH.read_bytes(),
    )

    sanitized = RedactionStage(security).redact(extraction)

    assert sanitized.candidates
    joined = "\n".join(
        candidate.sanitized_text or "" for candidate in sanitized.candidates
    )
    assert "[REDACTED:SECRET:" in joined
    assert "[REDACTED:PII:" in joined
    for raw_secret in RAW_SECRETS:
        assert raw_secret not in joined

    secret_candidates = [
        candidate for candidate in sanitized.candidates if candidate.redaction_findings
    ]
    assert secret_candidates
    assert all(
        candidate.redaction_status == "redacted" for candidate in secret_candidates
    )
    assert any(
        candidate.sensitivity_class == "restricted" for candidate in secret_candidates
    )
    assert all(
        candidate.visibility_label == "invited_users"
        and candidate.corpus_eligibility_label == "review_required"
        and candidate.license_policy_label in {"allowed", "review_required"}
        for candidate in sanitized.candidates
    )


def test_unredacted_extraction_candidates_are_rejected_by_persistence_guard() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(engine)
        extraction = MarkdownExtractor().extract(
            _artifact(sensitivity_class="confidential"),
            FIXTURE_PATH.read_bytes(),
        )

        with Session(engine) as session:
            _add_minimal_graph(session)
            repository = ArtifactExtractionRepository(session)
            with pytest.raises(UnredactedCandidateError):
                repository.create_from_result(
                    extraction,
                    ingestion_run_id="ingestion:redaction",
                )
    finally:
        engine.dispose()


def test_redaction_and_license_events_persist_no_raw_secret_values() -> None:
    security = load_security_config(Path("config/security.yaml"))
    extraction = MarkdownExtractor().extract(
        _artifact(sensitivity_class="confidential"),
        FIXTURE_PATH.read_bytes(),
    )
    sanitized = RedactionStage(security).redact(extraction)
    redacted_candidate = next(
        candidate for candidate in sanitized.candidates if candidate.redaction_findings
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_minimal_graph(session)
            extraction_row = ArtifactExtractionRepository(
                session
            ).create_from_sanitized_result(
                sanitized,
                ingestion_run_id="ingestion:redaction",
            )
            redaction_rows = RedactionEventRepository(session).create_for_candidate(
                redacted_candidate,
                ingestion_run_id="ingestion:redaction",
            )
            LicenseFindingRepository(session).create_for_candidate(redacted_candidate)
            session.commit()

            assert extraction_row.sanitized_content_hash is not None
            assert redaction_rows
            event = session.scalar(select(RedactionEvent))
            finding = session.scalar(select(LicenseFinding))
            assert event is not None
            assert finding is not None
            assert event.rule_id
            assert event.redaction_type in {"secret", "pii"}
            assert event.marker.startswith("[REDACTED:")
            assert event.match_count >= 1
            assert event.corpus_eligibility_label == "review_required"
            assert event.visibility_label == "invited_users"
            assert event.sensitivity_class == redacted_candidate.sensitivity_class
            assert finding.license_policy_label in {"allowed", "review_required"}
            assert finding.corpus_eligibility_label == "review_required"

            persisted_text = "\n".join(
                str(row)
                for row in (
                    extraction_row.diagnostics,
                    event.marker,
                    event.location_locator,
                    event.sanitized_content_hash,
                    finding.license_expression,
                    finding.copyright_notice,
                )
            )
            for raw_secret in RAW_SECRETS:
                assert raw_secret not in persisted_text
    finally:
        engine.dispose()


def test_redaction_event_locator_is_sanitized_before_persistence() -> None:
    security = load_security_config(Path("config/security.yaml"))
    extraction = MarkdownExtractor().extract(
        _artifact(
            sensitivity_class="confidential",
            logical_locator="fixture:password=hunter2",
        ),
        FIXTURE_PATH.read_bytes(),
    )
    sanitized = RedactionStage(security).redact(extraction)
    redacted_candidate = next(
        candidate for candidate in sanitized.candidates if candidate.redaction_findings
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_minimal_graph(session)
            RedactionEventRepository(session).create_for_candidate(
                redacted_candidate,
                ingestion_run_id="ingestion:redaction",
            )
            session.commit()

            event = session.scalar(select(RedactionEvent))
            assert event is not None
            assert event.location_locator == "fixture:[redacted]"
            assert "password" not in event.location_locator.lower()
            assert "hunter2" not in event.location_locator
    finally:
        engine.dispose()


def _artifact(
    *,
    sensitivity_class: str = "internal",
    logical_locator: str = "fixture:unsafe.md",
) -> ArtifactExtractionContext:
    return ArtifactExtractionContext(
        artifact_id="artifact:redaction",
        source_id="source:redaction",
        source_version_id="source-version:redaction",
        path="unsafe.md",
        logical_locator=logical_locator,
        source_type="local_directory",
        artifact_role="documentation",
        language="markdown",
        extractor_profile="docs_default",
        visibility_label="invited_users",
        sensitivity_class=sensitivity_class,
        license_policy_label="review_required",
        corpus_eligibility_label="review_required",
    )


def _add_minimal_graph(session: Session) -> None:
    session.add(
        Source(
            id="source:redaction",
            config_key="redaction-source",
            name="Redaction Source",
            source_type="local_directory",
        )
    )
    session.add(
        SourceVersion(
            id="source-version:redaction",
            source_id="source:redaction",
            version_label="snapshot",
            is_current=True,
        )
    )
    session.add(
        IngestionRun(
            id="ingestion:redaction",
            source_id="source:redaction",
            source_version_id="source-version:redaction",
            requested_ref="snapshot",
            status="completed",
            stats={},
        )
    )
    session.add(
        Artifact(
            id="artifact:redaction",
            artifact_key="unsafe.md",
            artifact_type="document",
            artifact_role="documentation",
            path="unsafe.md",
            source_id="source:redaction",
            source_version_id="source-version:redaction",
            source_type="local_directory",
            visibility_label="invited_users",
            sensitivity_class="confidential",
            license_policy_status="review_required",
            redaction_status="redacted",
        )
    )
    session.flush()
