"""Data classification and handling policy.

Every field stored or processed by the pipeline is assigned a classification.
The classification drives masking, export, retention, and whether a value may
be sent to an external model. Unknown fields default to ``INTERNAL`` (fail
closed would be too disruptive for additive columns; sensitive names are
matched explicitly below).
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Iterable


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


_ORDER = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}

# Fields that are personally identifiable or secret-bearing.
_RESTRICTED = {
    "email",
    "phone",
    "purchase_contact_email",
    "purchase_contact_phone",
    "password",
    "secret",
    "secret_encrypted",
    "api_key",
    "token",
    "aadhaar",
    "pan",
    "gstin",
    "credit_card",
}
_CONFIDENTIAL = {
    "name",
    "company",
    "address",
    "context",
    "notes",
    "linkedin_company",
    "linkedin_profiles",
    "purchase_contact_name",
    "purchase_contact_role",
    "content",
    "message",
}
_INTERNAL = {
    "id",
    "user_id",
    "domain",
    "intent",
    "source",
    "gcs_path",
    "status",
    "is_active",
    "is_connected",
    "created_at",
    "updated_at",
    "extracted_at",
    "last_login_at",
    "last_checked_at",
    "sent_at",
}

_SENSITIVE_NAME = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|credential|cookie)",
    re.IGNORECASE,
)


def classify_field(name: str) -> DataClassification:
    key = (name or "").strip().lower()
    if key in _RESTRICTED or _SENSITIVE_NAME.search(key):
        return DataClassification.RESTRICTED
    if key in _CONFIDENTIAL:
        return DataClassification.CONFIDENTIAL
    if key in _INTERNAL:
        return DataClassification.INTERNAL
    return DataClassification.INTERNAL


def max_class(values: Iterable[DataClassification]) -> DataClassification:
    return max(values, key=lambda c: _ORDER[c], default=DataClassification.PUBLIC)


def classify_record(record: dict[str, Any]) -> DataClassification:
    return max_class(classify_field(name) for name in record)


def is_pii_field(name: str) -> bool:
    return classify_field(name) == DataClassification.RESTRICTED


def may_leave_environment(name: str) -> bool:
    """Whether a field may be sent to an external (non-GCP) model provider."""
    return classify_field(name) in {
        DataClassification.PUBLIC,
        DataClassification.INTERNAL,
    }


def policy_summary() -> dict[str, list[str]]:
    return {
        DataClassification.RESTRICTED.value: sorted(_RESTRICTED),
        DataClassification.CONFIDENTIAL.value: sorted(_CONFIDENTIAL),
        DataClassification.INTERNAL.value: sorted(_INTERNAL),
    }
