from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.config import load_security_config
from idp_brain.ingestion.extractors import ArtifactExtractionContext, MarkdownExtractor
from idp_brain.ingestion.redaction_stage import RedactionStage
from idp_brain.models import ArtifactExtraction, RedactionEvent
from idp_brain.repositories import (
    ArtifactExtractionRepository,
    RedactionEventRepository,
)

from .conftest import assert_no_forbidden_ingestion_text


def test_redaction_precedes_persistence_and_event_metadata_is_sanitized(
    artifact_context_factory: Callable[..., ArtifactExtractionContext],
    add_ingestion_graph,
    ingestion_session_factory: sessionmaker[Session],
) -> None:
    extraction = MarkdownExtractor().extract(
        artifact_context_factory(
            "guide.md",
            "documentation",
            locator="fixture:password=hunter2-ingestion",
        ),
        Path("tests/fixtures/ingestion/local/guide.md").read_bytes(),
    )
    redacted = RedactionStage(
        load_security_config(Path("config/security.yaml"))
    ).redact(extraction)

    with ingestion_session_factory() as session:
        add_ingestion_graph(session)
        ArtifactExtractionRepository(session).create_from_sanitized_result(
            redacted,
            ingestion_run_id="ingestion:run",
        )
        redaction_repository = RedactionEventRepository(session)
        for candidate in redacted.candidates:
            redaction_repository.create_for_candidate(
                candidate,
                ingestion_run_id="ingestion:run",
            )
        session.commit()

        persisted = [
            str(extraction_row.diagnostics)
            for extraction_row in session.scalars(select(ArtifactExtraction)).all()
        ]
        persisted.extend(
            event.location_locator
            for event in session.scalars(select(RedactionEvent)).all()
        )
        assert_no_forbidden_ingestion_text(session)

    assert any("[redacted]" in value for value in persisted)
