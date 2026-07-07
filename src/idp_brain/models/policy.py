"""Global corpus eligibility policy metadata.

This module intentionally models corpus-wide retrieval eligibility only. The
MVP has invited users who share the same approved corpus, so no caller-specific
or role-based policy models belong here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, TimestampMixin, utc_now

DEFAULT_SOURCE_ALLOWLISTED: Final[bool] = False
DEFAULT_VISIBILITY_LABEL: Final[str] = "invited_users"
DEFAULT_SENSITIVITY_CLASS: Final[str] = "unknown"
DEFAULT_LICENSE_POLICY_STATUS: Final[str] = "unknown"
DEFAULT_REDACTION_STATUS: Final[str] = "unknown"

ALLOWED_RETRIEVABLE_LICENSE_IDS: Final[tuple[str, ...]] = ("MIT", "Apache-2.0")
LICENSE_POLICY_STATUSES: Final[tuple[str, ...]] = (
    "unknown",
    "review_required",
    "allowed",
    "denied",
)
SENSITIVITY_CLASSES: Final[tuple[str, ...]] = (
    "unknown",
    "public",
    "internal",
    "confidential",
    "restricted",
)
VISIBILITY_LABELS: Final[tuple[str, ...]] = ("invited_users",)
REDACTION_STATUSES: Final[tuple[str, ...]] = (
    "unknown",
    "not_required",
    "redacted",
    "blocked",
)


def _quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


LICENSE_POLICY_STATUS_CHECK: Final[str] = (
    f"license_policy_status IN ({_quoted_values(LICENSE_POLICY_STATUSES)})"
)
SENSITIVITY_CLASS_CHECK: Final[str] = (
    f"sensitivity_class IN ({_quoted_values(SENSITIVITY_CLASSES)})"
)
VISIBILITY_LABEL_CHECK: Final[str] = (
    f"visibility_label IN ({_quoted_values(VISIBILITY_LABELS)})"
)
REDACTION_STATUS_CHECK: Final[str] = (
    f"redaction_status IN ({_quoted_values(REDACTION_STATUSES)})"
)
LICENSE_ID_ALLOWED_CHECK: Final[str] = (
    "(license_policy_status != 'allowed' "
    f"OR license_id IN ({_quoted_values(ALLOWED_RETRIEVABLE_LICENSE_IDS)}))"
)
LICENSE_ID_NULLABILITY_CHECK: Final[str] = (
    "(license_id IS NOT NULL "
    "OR license_policy_status IN ('unknown', 'review_required'))"
)


class CorpusEligibilityMixin:
    """Corpus eligibility labels required before future retrieval subqueries."""

    source_allowlisted: Mapped[bool] = mapped_column(
        Boolean,
        default=DEFAULT_SOURCE_ALLOWLISTED,
        nullable=False,
    )
    visibility_label: Mapped[str] = mapped_column(
        String(100),
        default=DEFAULT_VISIBILITY_LABEL,
        nullable=False,
    )
    sensitivity_class: Mapped[str] = mapped_column(
        String(100),
        default=DEFAULT_SENSITIVITY_CLASS,
        nullable=False,
    )
    license_policy_status: Mapped[str] = mapped_column(
        String(100),
        default=DEFAULT_LICENSE_POLICY_STATUS,
        nullable=False,
    )
    license_id: Mapped[str | None] = mapped_column(String(100))
    redaction_status: Mapped[str] = mapped_column(
        String(100),
        default=DEFAULT_REDACTION_STATUS,
        nullable=False,
    )


def corpus_eligibility_constraints(table_name: str) -> tuple[CheckConstraint, ...]:
    """Return reusable fail-closed corpus eligibility check constraints."""

    return (
        CheckConstraint(
            LICENSE_POLICY_STATUS_CHECK,
            name=f"{table_name}_license_policy_status_valid",
        ),
        CheckConstraint(
            SENSITIVITY_CLASS_CHECK,
            name=f"{table_name}_sensitivity_class_valid",
        ),
        CheckConstraint(
            VISIBILITY_LABEL_CHECK,
            name=f"{table_name}_visibility_label_valid",
        ),
        CheckConstraint(
            REDACTION_STATUS_CHECK,
            name=f"{table_name}_redaction_status_valid",
        ),
        CheckConstraint(
            LICENSE_ID_ALLOWED_CHECK,
            name=f"{table_name}_allowed_license_id_valid",
        ),
        CheckConstraint(
            LICENSE_ID_NULLABILITY_CHECK,
            name=f"{table_name}_license_id_presence_valid",
        ),
    )


class CorpusPolicyDefault(TimestampMixin, Base):
    """Canonical global defaults for future corpus eligibility filtering."""

    __tablename__ = "corpus_policy_defaults"
    __table_args__ = (
        CheckConstraint(
            "source_allowlist_default = false",
            name="source_allowlist_default_fail_closed",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_allowlist_default: Mapped[bool] = mapped_column(
        Boolean,
        default=DEFAULT_SOURCE_ALLOWLISTED,
        nullable=False,
    )
    allowed_license_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: list(ALLOWED_RETRIEVABLE_LICENSE_IDS),
        nullable=False,
    )
    allowed_license_policy_statuses: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: ["allowed"],
        nullable=False,
    )
    allowed_sensitivity_classes: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: ["public"],
        nullable=False,
    )
    allowed_visibility_labels: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: list(VISIBILITY_LABELS),
        nullable=False,
    )
    allowed_redaction_statuses: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: ["not_required", "redacted"],
        nullable=False,
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
