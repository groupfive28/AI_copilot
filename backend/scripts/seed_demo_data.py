"""
Seeds a handful of realistic demo applications into penta_application, for
demoing the operations dashboard before the OCR/verification pipeline is
built. Covers all 5 application statuses and all 5 document states
(pending/verified/mismatch/not_found/error), plus both check types.

Uses fixed UUIDs for the demo rows, so rerunning this script deletes and
re-inserts the same rows instead of accumulating duplicates - safe to run
as many times as needed ("reseed").

Usage:
    python scripts/seed_demo_data.py

Connection: reads DATABASE_URL from backend/.env, same convention as the
other scripts in this directory.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
DATABASE_URL = os.environ["DATABASE_URL"]

now = datetime.now(timezone.utc)

# Fixed IDs so reruns replace these exact rows rather than duplicating them.
APPLICATIONS = [
    {
        "id": "a0000000-0000-4000-8000-000000000001",
        "company_name": "Alpha Logistics Ltd",
        "rc": "RC1010101",
        "status": "received",
        "days_ago": 1,
        "documents": {
            "cac_certificate": None,
            "tin": None,
            "nin": None,
            "bvn": None,
            "voters_card": None,
            "passport_or_drivers_license": None,
            "proof_of_address": None,
        },
    },
    {
        "id": "a0000000-0000-4000-8000-000000000002",
        "company_name": "Beacon Freight Nigeria",
        "rc": "RC2020202",
        "status": "processing",
        "days_ago": 2,
        "documents": {
            "cac_certificate": ("registry_lookup", "cac_tin_registry", "match", None),
            "tin": ("registry_lookup", "cac_tin_registry", "match", None),
            "nin": None,
            "bvn": None,
        },
    },
    {
        "id": "a0000000-0000-4000-8000-000000000003",
        "company_name": "Crestline Traders",
        "rc": "RC3030303",
        "status": "escalated",
        "days_ago": 3,
        "documents": {
            "cac_certificate": None,
            "nin": (
                "registry_lookup",
                "nin_registry",
                "mismatch",
                {"field": "last_name", "submitted": "Okafor", "registry": "Okaforr"},
            ),
            "bvn": ("registry_lookup", "bvn_registry", "not_found", None),
        },
    },
    {
        "id": "a0000000-0000-4000-8000-000000000004",
        "company_name": "Delta Micro Bank Agents",
        "rc": "RC4040404",
        "status": "approved",
        "days_ago": 4,
        "documents": {
            "cac_certificate": ("registry_lookup", "cac_tin_registry", "match", None),
            "tin": ("registry_lookup", "cac_tin_registry", "match", None),
        },
    },
    {
        "id": "a0000000-0000-4000-8000-000000000005",
        "company_name": "Everline Textiles Co",
        "rc": "RC5050505",
        "status": "rejected",
        "days_ago": 5,
        "documents": {
            "nin": (
                "registry_lookup",
                "nin_registry",
                "mismatch",
                {"field": "date_of_birth", "submitted": "1990-04-12", "registry": "1989-04-12"},
            ),
            "bvn": ("registry_lookup", "bvn_registry", "error", {"reason": "registry lookup timed out"}),
            "passport_or_drivers_license": ("face_verification", None, "mismatch", {"reason": "face did not match other submitted documents"}),
        },
    },
]


def main() -> None:
    engine = create_engine(DATABASE_URL)
    app_ids = [app["id"] for app in APPLICATIONS]

    with engine.begin() as conn:
        # Delete-then-insert on the fixed IDs above, so reruns replace
        # cleanly instead of piling up duplicate demo companies.
        conn.execute(
            text("DELETE FROM penta_application.verification_results WHERE application_id::text = ANY(:ids)"),
            {"ids": app_ids},
        )
        conn.execute(
            text("DELETE FROM penta_application.extracted_fields WHERE application_id::text = ANY(:ids)"),
            {"ids": app_ids},
        )
        conn.execute(
            text("DELETE FROM penta_application.applications WHERE id::text = ANY(:ids)"),
            {"ids": app_ids},
        )

        for app in APPLICATIONS:
            created_at = now - timedelta(days=app["days_ago"])

            conn.execute(
                text("""
                    INSERT INTO penta_application.applications
                        (id, cac_registration_number, company_name, business_type, tin,
                         signatory_full_name, signatory_email, signatory_phone_number, signatory_designation,
                         status, created_at, updated_at)
                    VALUES (:id, :rc, :company, 'private_company_limited_by_shares', :rc,
                            'Demo Signatory', 'demo-signatory@example.com', '+2340000000000', 'Director',
                            :status, :created, :created)
                """),
                {"id": app["id"], "rc": app["rc"], "company": app["company_name"], "status": app["status"], "created": created_at},
            )

            for category, verification in app["documents"].items():
                document_id = str(uuid.uuid4())
                conn.execute(
                    text("""
                        INSERT INTO penta_application.extracted_fields
                            (id, application_id, document_id, document_category, extracted_data, confidence_score, created_at)
                        VALUES (gen_random_uuid(), :app_id, :doc_id, :category, '{}'::jsonb, NULL, :created)
                    """),
                    {"app_id": app["id"], "doc_id": document_id, "category": category, "created": created_at},
                )

                if verification is not None:
                    check_type, registry_table, status, details = verification
                    conn.execute(
                        text("""
                            INSERT INTO penta_application.verification_results
                                (application_id, document_id, check_type, registry_table, status, discrepancy_details, created_at)
                            VALUES (:app_id, :doc_id, :check_type, :registry_table, :status, :details, :created)
                        """),
                        {
                            "app_id": app["id"],
                            "doc_id": document_id,
                            "check_type": check_type,
                            "registry_table": registry_table,
                            "status": status,
                            "details": json.dumps(details) if details else None,
                            "created": created_at,
                        },
                    )

    print(f"Seeded {len(APPLICATIONS)} demo applications:")
    for app in APPLICATIONS:
        print(f"  {app['company_name']} ({app['status']}) -> {app['id']}")


if __name__ == "__main__":
    main()
