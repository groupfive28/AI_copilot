from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.operations.schemas import (
    ApplicationDetail,
    ApplicationDocument,
    ApplicationListItem,
    ApplicationListResponse,
    ApplicationSummary,
    ApplicationVerificationFailures,
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
            SELECT id, company_name, cac_registration_number, status, created_at
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

    return ApplicationDetail(**application_row, documents=documents)


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
            vr.created_at
        FROM penta_application.verification_results vr
        JOIN penta_application.applications a ON a.id = vr.application_id
        LEFT JOIN penta_application.extracted_fields ef
            ON ef.document_id = vr.document_id AND ef.application_id = vr.application_id
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
        grouped[app_id].failures.append(
            VerificationFailureDetail(
                document_category=row["document_category"],
                check_type=row["check_type"],
                registry_table=row["registry_table"],
                status=row["status"],
                discrepancy_details=row["discrepancy_details"],
                created_at=row["created_at"],
            )
        )

    return VerificationResultsResponse(items=list(grouped.values()))
