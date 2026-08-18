from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import create_engine, text

from sigverify.config import settings

_engine = None


def _get_engine():
    """Lazy, same reasoning as faceverify/db.py's _get_engine()."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def save_signature_verification_result(
    *,
    application_id: str,
    document_id: str,
    status: str,
    discrepancy_details: dict[str, Any] | None,
) -> None:
    """
    registry_table is always NULL here - check_type='signature_verification'
    rows are required to have a NULL registry_table by
    verification_results_registry_table_required (see
    backend/scripts/sql/001_create_penta_application_schema.sql).
    """
    with _get_engine().begin() as conn:
        conn.execute(
            text("""
                INSERT INTO penta_application.verification_results
                    (id, application_id, document_id, check_type, registry_table, status, discrepancy_details, created_at)
                VALUES (gen_random_uuid(), :application_id, :document_id, 'signature_verification', NULL, :status, :discrepancy_details, now())
            """),
            {
                "application_id": application_id,
                "document_id": document_id,
                "status": status,
                "discrepancy_details": _to_jsonb_param(discrepancy_details),
            },
        )


def _to_jsonb_param(value: dict[str, Any] | None):
    import json

    return json.dumps(value) if value is not None else None


def new_document_id() -> str:
    """Same reasoning as faceverify/db.py's new_document_id() - there's no
    one extracted_fields row this result is "about"."""
    return str(uuid.uuid4())
