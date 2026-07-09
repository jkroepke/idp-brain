"""Extractor interfaces and built-in parser registry."""

from idp_brain.ingestion.extractors.base import (
    EXTRACTION_SCHEMA_VERSION,
    ArtifactExtractionContext,
    ExtractionCandidate,
    ExtractionDiagnostic,
    ExtractionResult,
    Extractor,
    LineRange,
)
from idp_brain.ingestion.extractors.html import HtmlExtractor
from idp_brain.ingestion.extractors.json import JsonExtractor
from idp_brain.ingestion.extractors.json_schema import JsonSchemaExtractor
from idp_brain.ingestion.extractors.markdown import MarkdownExtractor
from idp_brain.ingestion.extractors.openapi import OpenApiExtractor
from idp_brain.ingestion.extractors.registry import ExtractorRegistry
from idp_brain.ingestion.extractors.source_code import SourceCodeExtractor
from idp_brain.ingestion.extractors.text import TextExtractor
from idp_brain.ingestion.extractors.toml import TomlExtractor
from idp_brain.ingestion.extractors.yaml import YamlExtractor

__all__ = [
    "EXTRACTION_SCHEMA_VERSION",
    "ArtifactExtractionContext",
    "ExtractionCandidate",
    "ExtractionDiagnostic",
    "ExtractionResult",
    "Extractor",
    "ExtractorRegistry",
    "HtmlExtractor",
    "JsonExtractor",
    "JsonSchemaExtractor",
    "LineRange",
    "MarkdownExtractor",
    "OpenApiExtractor",
    "SourceCodeExtractor",
    "TextExtractor",
    "TomlExtractor",
    "YamlExtractor",
]
