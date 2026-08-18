import uuid
from datetime import UTC, datetime

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.storage import replace_document
from app.onboarding.models import Application
from app.operations.models import AuditLogEntry
from app.operations.schemas import (
    ApplicationDetail,
    ApplicationDocument,
    ApplicationListItem,
    ApplicationListResponse,
    ApplicationSummary,
    ApplicationVerificationFailures,
    AuditLogEntryOut,
    BiometricCheckDetail,
    VerificationFailureDetail,
    VerificationResultsResponse,
)

# Failure statuses a compliance officer needs to see - errors included, since
# an unresolved check needs attention just as much as a real mismatch.
FAILED_STATUSES = ("mismatch", "not_found", "error")

# verification_results.status uses "match"; the per-document badge in the
# detail view uses "verified" - map between them rather than passing the raw
# DB value straight into a DocumentState field that doesn't include "match".
_VERIFICATION_STATUS_TO_DOCUMENT_STATE = {
    "match": "verified",
    "mismatch": "mismatch",
    "not_found": "not_found",
    "error": "error",
}

def _format_director_name(first_name: str | None, middle_name: str | None, last_name: str | None) -> str | None:
    parts = [p for p in (first_name, middle_name, last_name) if p]
    return " ".join(parts) if parts else None


_SORT_COLUMNS = {
    "company_name": "company_name",
    "cac_registration_number": "cac_registration_number",
    "status": "status",
    "created_at": "created_at",
}


def list_applications(
    db: Session,
    status_filter: str | None,
    sort_by: str,
    sort_dir: str,
) -> ApplicationListResponse:
    column = _SORT_COLUMNS.get(sort_by, "created_at")
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"

    rows = db.execute(
        text(f"""
            SELECT id, company_name, cac_registration_number, status, pipeline_stage, created_at
            FROM penta_application.applications
            WHERE (:status IS NULL OR status = :status)
            ORDER BY {column} {direction}
        """),  # noqa: S608 - column/direction come from the fixed allow-list above, not user input
        {"status": status_filter},
    ).mappings().all()

    summary_row = db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status IN ('received', 'processing', 'escalated')) AS pending_review,
                (
                    SELECT COUNT(DISTINCT application_id)
                    FROM penta_application.verification_results
                    WHERE status IN ('mismatch', 'not_found', 'error')
                ) AS verification_failures
            FROM penta_application.applications
        """)
    ).mappings().one()

    return ApplicationListResponse(
        summary=ApplicationSummary(**summary_row),
        items=[ApplicationListItem(**row) for row in rows],
    )


def get_application_detail(db: Session, application_id: str) -> ApplicationDetail | None:
    application_row = db.execute(
        text("SELECT * FROM penta_application.applications WHERE id = :id"),
        {"id": application_id},
    ).mappings().first()

    if application_row is None:
        return None

    # For each document, the latest registry_lookup result (if any) decides
    # its state. face_verification results aren't per-document-category in
    # the same sense, so they don't drive this badge - see operations router
    # docstring.
    document_rows = db.execute(
        text("""
            SELECT
                ef.document_id,
                ef.document_category,
                ef.confidence_score,
                vr.status AS verification_status,
                vr.registry_table,
                vr.discrepancy_details
            FROM penta_application.extracted_fields ef
            LEFT JOIN LATERAL (
                SELECT status, registry_table, discrepancy_details
                FROM penta_application.verification_results v
                WHERE v.document_id = ef.document_id AND v.check_type = 'registry_lookup'
                ORDER BY v.created_at DESC
                LIMIT 1
            ) vr ON true
            WHERE ef.application_id = :id
            ORDER BY ef.document_category
        """),
        {"id": application_id},
    ).mappings().all()

    documents = [
        ApplicationDocument(
            document_id=row["document_id"],
            document_category=row["document_category"],
            state=_VERIFICATION_STATUS_TO_DOCUMENT_STATE.get(row["verification_status"], "pending"),
            confidence_score=row["confidence_score"],
            registry_table=row["registry_table"],
            discrepancy_details=row["discrepancy_details"],
        )
        for row in document_rows
    ]

    # face_verification/signature_verification results, every status (not
    # just failures - see BiometricCheckDetail's docstring for why these
    # can't just be folded into `documents` above). director_index lives
    # inside discrepancy_details (there's no dedicated column for it - see
    # verification/service.py's pipeline callers), so it's pulled out of
    # the JSONB to join against application_directors for the name.
    biometric_rows = db.execute(
        text("""
            SELECT
                vr.check_type,
                (vr.discrepancy_details->>'director_index')::int AS director_index,
                ad.first_name,
                ad.middle_name,
                ad.last_name,
                vr.status,
                vr.discrepancy_details,
                vr.created_at
            FROM penta_application.verification_results vr
            LEFT JOIN penta_application.application_directors ad
                ON ad.application_id = vr.application_id
                AND ad.director_index = (vr.discrepancy_details->>'director_index')::int
            WHERE vr.application_id = :id AND vr.check_type IN ('face_verification', 'signature_verification')
            ORDER BY vr.created_at
        """),
        {"id": application_id},
    ).mappings().all()

    biometric_checks = [
        BiometricCheckDetail(
            check_type=row["check_type"],
            director_index=row["director_index"],
            director_name=_format_director_name(row["first_name"], row["middle_name"], row["last_name"]),
            status=row["status"],
            discrepancy_details=row["discrepancy_details"],
            created_at=row["created_at"],
        )
        for row in biometric_rows
    ]

    audit_rows = db.execute(
        text("""
            SELECT id, event_type, event_details, created_at
            FROM penta_application.audit_log
            WHERE application_id = :id
            ORDER BY created_at DESC
        """),
        {"id": application_id},
    ).mappings().all()
    audit_log = [AuditLogEntryOut(**row) for row in audit_rows]

    return ApplicationDetail(
        **application_row, documents=documents, biometric_checks=biometric_checks, audit_log=audit_log
    )


def update_application_status(
    db: Session,
    application_id: str,
    decision: str,
    note: str | None,
    admin_email: str,
) -> Application | None:
    """Manual operator decision (approve/reject/escalate) from the
    dashboard. Recorded in audit_log with who made the call and why -
    status_changed is a new event_type, but audit_log has no CHECK
    constraint on event_type (see the DDL), so this doesn't need a schema
    change."""
    application = db.get(Application, application_id)
    if application is None:
        return None

    previous_status = application.status
    now = datetime.now(UTC)
    application.status = decision
    application.updated_at = now

    db.add(
        AuditLogEntry(
            id=uuid.uuid4(),
            application_id=application.id,
            event_type="status_changed",
            event_details={
                "from_status": previous_status,
                "to_status": decision,
                "note": note,
                "changed_by": admin_email,
            },
            created_at=now,
        )
    )
    db.commit()
    db.refresh(application)
    return application


def reupload_document(
    db: Session,
    application_id: str,
    document_category: str,
    filename: str,
    content: bytes,
    content_type: str | None,
    note: str | None,
    admin_email: str,
) -> Application | None:
    """Admin-initiated correction for one document slot - see
    app/core/storage.py's replace_document for why the stale document is
    deleted first rather than left alongside the new one.

    Also clears every extracted_fields and verification_results row for
    the WHOLE application, not just this document_category - confirmed by
    testing this live: ocr/src/penta/ingest.py's list_submitted_documents
    reprocesses every blob currently in Storage on every /extract call,
    with no concept of "only the one that changed," so the pipeline re-run
    triggered below would otherwise produce a second, fresh set of rows
    sitting alongside the old ones rather than replacing them. Left
    uncleared, auto_decide_application would see both the old "mismatch"
    and the new "match" in the same status set and escalate again even
    though the correction fixed it - which is exactly what happened the
    first time this was tested. Safe to clear everything: the upcoming
    pipeline run regenerates a complete, current set for every document
    still in Storage, corrected slot included.

    Resets status to "processing" and clears pipeline_stage so the
    dashboard reflects that this application is back in flight rather than
    still showing its old (now stale) escalated/rejected verdict while the
    re-run pipeline is mid-flight. The caller is responsible for actually
    triggering that pipeline re-run (backend/app/operations/router.py, as
    a BackgroundTask) - this function only handles the Storage swap, the
    stale-data cleanup, the status reset, and the audit trail."""
    application = db.get(Application, application_id)
    if application is None:
        return None

    blob_name = replace_document(application_id, document_category, filename, content, content_type)

    db.execute(
        text("DELETE FROM penta_application.verification_results WHERE application_id = :id"),
        {"id": application_id},
    )
    db.execute(
        text("DELETE FROM penta_application.extracted_fields WHERE application_id = :id"),
        {"id": application_id},
    )

    now = datetime.now(UTC)
    application.status = "processing"
    application.pipeline_stage = None
    application.updated_at = now
    db.add(
        AuditLogEntry(
            id=uuid.uuid4(),
            application_id=application.id,
            event_type="document_reuploaded",
            event_details={
                "document_category": document_category,
                "filename": filename,
                "storage_path": blob_name,
                "note": note,
                "uploaded_by": admin_email,
            },
            created_at=now,
        )
    )
    db.commit()
    db.refresh(application)
    return application


def list_verification_failures(db: Session, failed_only: bool) -> VerificationResultsResponse:
    status_clause = "vr.status IN :failed_statuses" if failed_only else "TRUE"

    query = text(f"""
        SELECT
            a.id AS application_id,
            a.company_name,
            a.status AS application_status,
            ef.document_category,
            vr.check_type,
            vr.registry_table,
            vr.status,
            vr.discrepancy_details,
            vr.created_at,
            (vr.discrepancy_details->>'director_index')::int AS director_index,
            ad.first_name,
            ad.middle_name,
            ad.last_name
        FROM penta_application.verification_results vr
        JOIN penta_application.applications a ON a.id = vr.application_id
        LEFT JOIN penta_application.extracted_fields ef
            ON ef.document_id = vr.document_id AND ef.application_id = vr.application_id
        LEFT JOIN penta_application.application_directors ad
            ON ad.application_id = vr.application_id
            AND ad.director_index = (vr.discrepancy_details->>'director_index')::int
        WHERE {status_clause}
        ORDER BY a.company_name, vr.created_at DESC
    """)  # noqa: S608 - status_clause is a fixed literal, not user input
    if failed_only:
        query = query.bindparams(bindparam("failed_statuses", expanding=True))

    rows = db.execute(
        query,
        {"failed_statuses": FAILED_STATUSES} if failed_only else {},
    ).mappings().all()

    grouped: dict[str, ApplicationVerificationFailures] = {}
    for row in rows:
        app_id = str(row["application_id"])
        if app_id not in grouped:
            grouped[app_id] = ApplicationVerificationFailures(
                application_id=row["application_id"],
                company_name=row["company_name"],
                status=row["application_status"],
                failures=[],
            )

        document_category = row["document_category"]
        if document_category is None and row["check_type"] == "face_verification":
            # face_verification rows have no real document_id to join
            # against (face-verification/db.py's new_document_id() is a
            # fresh uuid, not tied to any extracted_fields row - there's no
            # single document a face comparison "belongs to" the way a
            # registry_lookup belongs to the document it read). The
            # director's passport photo is the subject being verified (the
            # government ID is what it's compared against, already visible
            # in discrepancy_details), so that's the category shown here -
            # "director_passport_photo" is the same real Storage category
            # name used everywhere else (face-verification/storage.py),
            # not a made-up one.
            document_category = "director_passport_photo"
        elif document_category is None and row["check_type"] == "signature_verification":
            # Same reasoning as the face_verification case above -
            # signature-verification/db.py's new_document_id() is also a
            # fresh uuid with nothing to join against. The director's
            # signature specimen is the subject being verified (the
            # government ID it's compared against is already visible in
            # discrepancy_details).
            document_category = "director_signature_specimen"

        grouped[app_id].failures.append(
            VerificationFailureDetail(
                document_category=document_category,
                check_type=row["check_type"],
                registry_table=row["registry_table"],
                status=row["status"],
                discrepancy_details=row["discrepancy_details"],
                created_at=row["created_at"],
                director_index=row["director_index"],
                director_name=_format_director_name(row["first_name"], row["middle_name"], row["last_name"]),
            )
        )

    return VerificationResultsResponse(items=list(grouped.values()))
