"""Supabase persistence for extracted document data (see penta.ingest).

Writes into the existing shared schema — applications / extracted_fields /
audit_log. This service does not own or create `applications`: that table
is populated elsewhere, when the application itself (company name, CAC
number, TIN, signatory) is created, before any document is ever uploaded.
We only ever reference an existing application_id, never insert one.

- extracted_fields: one row per extraction attempt (see
  count_prior_extractions — re-extractions add a new row, they don't
  overwrite). Confirmed columns: application_id, document_id,
  document_category, extracted_data (jsonb), confidence_score, created_at
  — no status/error/filename columns, so those live inside extracted_data
  (see penta.ingest) or in audit_log instead.
- audit_log: extraction failures, re-extractions, and suspected
  document-type mismatches.
- verification_results is deliberately NOT written here: its check_type is
  constrained to ('registry_lookup', 'face_verification') — real
  downstream business checks, not this service's OCR-confidence heuristic.
  Whatever later builds those checks should write there directly.
- applications.status is constrained to
  ('received', 'processing', 'escalated', 'approved', 'rejected') — a
  business workflow this service only ever nudges forward once, from
  'received' to 'processing' (see mark_application_processing); the later
  states are for whatever runs registry_lookup/face_verification, not for
  us to guess at.

Uses the official Supabase Python SDK, authenticated with the secret
(service_role) key — no direct Postgres connection, so no database password
involved. This key bypasses Row Level Security entirely and must never be
exposed client-side; it lives only in this service's environment.
"""

from __future__ import annotations

from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from penta.config import settings

_client: Client | None = None


def _get_client() -> Client:
    """Lazy so importing this module (transitively, everything imports it)
    doesn't require Supabase credentials to exist yet — only an actual save
    does, at which point a missing/bad credential is a clear, contained
    failure instead of the whole app refusing to start."""
    global _client
    if _client is None:
        _client = create_client(
            settings.supabase_url,
            settings.supabase_secret_key,
            options=SyncClientOptions(schema=settings.supabase_schema),
        )
    return _client


def count_prior_extractions(application_id: str, document_category: str) -> int:
    """How many extracted_fields rows already exist for this document.
    Submitted files are never moved/deleted, so this — not Storage state —
    is how we know whether something's already been processed, and how
    many times."""
    response = (
        _get_client()
        .table("extracted_fields")
        .select("id")
        .eq("application_id", application_id)
        .eq("document_category", document_category)
        .execute()
    )
    return len(response.data)


def save_extraction(
    *,
    application_id: str,
    document_id: str,
    document_category: str,
    extracted_data: dict[str, Any],
    confidence_score: float,
) -> None:
    _get_client().table("extracted_fields").insert(
        {
            "application_id": application_id,
            "document_id": document_id,
            "document_category": document_category,
            "extracted_data": extracted_data,
            "confidence_score": confidence_score,
        }
    ).execute()


def save_audit_event(*, application_id: str, event_type: str, event_details: dict[str, Any]) -> None:
    _get_client().table("audit_log").insert(
        {"application_id": application_id, "event_type": event_type, "event_details": event_details}
    ).execute()


def mark_application_processing(application_id: str) -> None:
    """Advance applications.status from 'received' to 'processing' once
    extraction starts. Guarded to only fire on that exact transition, so a
    re-extraction call can never move an application backwards out of a
    later state (escalated/approved/rejected) it may already be in.

    Best-effort: status tracking is a courtesy, not the point of the
    extract endpoint/poller — a Supabase hiccup here shouldn't stop actual
    extraction (GCS + Document AI) from being attempted, so failures are
    logged rather than raised.
    """
    try:
        _get_client().table("applications").update({"status": "processing"}).eq("id", application_id).eq(
            "status", "received"
        ).execute()
    except Exception as exc:  # noqa: BLE001 - logged, not fatal
        print(f"failed to advance applications.status for {application_id}: {exc}")
