from __future__ import annotations

import mimetypes
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from google.cloud import storage

from penta.config import settings
from penta.db import count_prior_extractions, save_audit_event, save_extraction
from penta.docai import process_bytes

SUBMISSIONS_ROOT = "onboarding-applications"
SUPPORTED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


@dataclass
class ProcessResult:
    ok: bool
    document_category: str = ""
    filename: str = ""
    text: str | None = None
    entities: dict[str, str] = field(default_factory=dict)
    type_mismatch_suspected: bool = False
    attempt: int = 1
    error: str | None = None


def _log_secondary_event(**kwargs: object) -> None:
    """audit_log writes here are supplementary, not the primary record —
    save_extraction succeeding is what actually matters. A failure logging
    a secondary event (re-extraction note, mismatch flag) must never flip
    an already-successful extraction into a reported failure, which is
    exactly what happened when verification_results (a stricter, unrelated
    write) failed after a successful extracted_fields insert."""
    try:
        save_audit_event(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 - logged, not fatal
        print(f"failed to record audit event ({kwargs.get('event_type')}): {exc}")


def list_submitted_documents(
    client: storage.Client, bucket: storage.Bucket, application_id: str
) -> list[tuple[str, str, storage.Blob]]:
    """List (document_category, filename, blob) for everything currently
    submitted under this application. document_category comes straight
    from the folder name Storage already organizes uploads by — callers
    don't need to supply it separately."""
    prefix = f"{SUBMISSIONS_ROOT}/{application_id}/"
    submitted = []
    for blob in client.list_blobs(bucket, prefix=prefix):
        remainder = blob.name[len(prefix) :]
        if remainder.endswith("/") or not remainder:
            continue  # folder placeholder
        parts = remainder.split("/", 1)
        if len(parts) != 2:
            continue  # not nested under a category folder
        document_category, filename = parts
        if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        submitted.append((document_category, filename, blob))
    return submitted


def process_document(
    blob: storage.Blob,
    application_id: str,
    document_category: str,
    filename: str,
) -> ProcessResult:
    document_id = str(uuid.uuid4())
    attempt = 1  

    try:
        attempt = count_prior_extractions(application_id, document_category) + 1

        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type is None:
            raise ValueError(f"could not determine mime type for {filename}")

        has_type_specific_processor = document_category in settings.document_processors
        processor_id = settings.document_processors.get(document_category, settings.gcp_processor_id)
        if not processor_id:
            raise ValueError(f"no processor configured for document_category={document_category!r}")

        result = process_bytes(blob.download_as_bytes(), mime_type, processor_id)

        confidences = [e["confidence"] for e in result.raw_entities]
        max_confidence = max(confidences, default=0.0)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        type_mismatch_suspected = has_type_specific_processor and (
            not result.entities or max_confidence < settings.min_entity_confidence
        )

        save_extraction(
            application_id=application_id,
            document_id=document_id,
            document_category=document_category,
            extracted_data={
                **result.entities,
                "_filename": filename,
                "_attempt": attempt,
                "_type_mismatch_suspected": type_mismatch_suspected,
                "_text": result.text,
            },
            confidence_score=avg_confidence,
        )

        if attempt > 1:
            _log_secondary_event(
                application_id=application_id,
                event_type="re_extraction",
                event_details={
                    "document_id": document_id,
                    "filename": filename,
                    "document_category": document_category,
                    "attempt": attempt,
                },
            )

        if type_mismatch_suspected:
            _log_secondary_event(
                application_id=application_id,
                event_type="type_mismatch_suspected",
                event_details={
                    "document_id": document_id,
                    "filename": filename,
                    "document_category": document_category,
                    "max_confidence": max_confidence,
                    "min_required_confidence": settings.min_entity_confidence,
                },
            )

        return ProcessResult(
            ok=True,
            document_category=document_category,
            filename=filename,
            text=result.text,
            entities=result.entities,
            type_mismatch_suspected=type_mismatch_suspected,
            attempt=attempt,
        )
    except Exception as exc:  # noqa: BLE001 - reported to the caller, not raised
        _log_secondary_event(
            application_id=application_id,
            event_type="extraction_failed",
            event_details={
                "document_id": document_id,
                "filename": filename,
                "document_category": document_category,
                "attempt": attempt,
                "error": str(exc),
            },
        )
        return ProcessResult(
            ok=False, document_category=document_category, filename=filename, attempt=attempt, error=str(exc)
        )
