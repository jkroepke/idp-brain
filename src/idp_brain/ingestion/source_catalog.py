"""Read-only source catalog projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from idp_brain.config import load_sources_config
from idp_brain.config.models import SourcesConfig


@dataclass(frozen=True)
class SourceCatalogEntry:
    """Metadata displayed before any source fetching or ingestion work."""

    source_id: str
    source_type: str
    tracked_refs: tuple[str, ...]
    version_strategy: str
    extractor_profile: str
    source_priority: int
    visibility_label: str
    corpus_eligibility: str
    sensitivity_class: str
    license_policy: str
    refresh_cadence: str
    enabled: bool

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["tracked_refs"] = list(self.tracked_refs)
        return data


def load_source_catalog(config_path: Path) -> list[SourceCatalogEntry]:
    """Load source catalog metadata from a typed sources config file."""

    config = load_sources_config(config_path)
    return build_source_catalog(config)


def build_source_catalog(config: SourcesConfig) -> list[SourceCatalogEntry]:
    """Project source config into stable metadata-only catalog entries."""

    return [
        SourceCatalogEntry(
            source_id=source.source_id,
            source_type=source.source_type,
            tracked_refs=tuple(source.tracked_refs),
            version_strategy=source.version_strategy,
            extractor_profile=source.extractor_profile,
            source_priority=source.source_priority,
            visibility_label=source.visibility_label,
            corpus_eligibility=source.corpus_eligibility,
            sensitivity_class=source.sensitivity_class,
            license_policy=source.license_policy,
            refresh_cadence=source.refresh_cadence,
            enabled=source.enabled,
        )
        for source in config.sources
    ]
