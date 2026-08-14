CREATE SCHEMA IF NOT EXISTS penta_application;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE penta_application.applications (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cac_registration_number     TEXT NOT NULL,
    company_name                TEXT NOT NULL,
    date_of_registration        DATE,
    business_type               TEXT NOT NULL,
    tin                         TEXT NOT NULL,
    signatory_full_name         TEXT NOT NULL,
    signatory_email             TEXT NOT NULL,
    signatory_phone_number      TEXT NOT NULL,
    signatory_designation       TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'received'
        CONSTRAINT applications_status_valid
        CHECK (status IN ('received', 'processing', 'escalated', 'approved', 'rejected')),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE penta_application.extracted_fields (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id      UUID NOT NULL REFERENCES penta_application.applications(id),
    document_id         UUID NOT NULL,
    document_category   TEXT NOT NULL,
    extracted_data       JSONB NOT NULL,
    confidence_score     NUMERIC(5,4),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX extracted_fields_application_id_idx ON penta_application.extracted_fields(application_id);
CREATE INDEX extracted_fields_document_id_idx ON penta_application.extracted_fields(document_id);

CREATE TABLE penta_application.verification_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id      UUID NOT NULL REFERENCES penta_application.applications(id),
    document_id         UUID NOT NULL,
    check_type          TEXT NOT NULL
        CONSTRAINT verification_results_check_type_valid
        CHECK (check_type IN ('registry_lookup', 'face_verification')),
    registry_table       TEXT
        CONSTRAINT verification_results_registry_table_valid
        CHECK (
            registry_table IS NULL OR registry_table IN (
                'nin_registry',
                'bvn_registry',
                'voters_id_registry',
                'passport_registry',
                'drivers_license_registry',
                'national_id_registry',
                'cac_tin_registry'
            )
        ),
    status               TEXT NOT NULL
        CONSTRAINT verification_results_status_valid
        CHECK (status IN ('match', 'mismatch', 'not_found', 'error')),
    discrepancy_details   JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT verification_results_registry_table_required
        CHECK (
            (check_type = 'registry_lookup'   AND registry_table IS NOT NULL) OR
            (check_type = 'face_verification' AND registry_table IS NULL)
        )
);

CREATE INDEX verification_results_application_id_idx ON penta_application.verification_results(application_id);
CREATE INDEX verification_results_document_id_idx ON penta_application.verification_results(document_id);

CREATE TABLE penta_application.audit_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id   UUID NOT NULL REFERENCES penta_application.applications(id),
    event_type       TEXT NOT NULL,
    event_details     JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX audit_log_application_id_idx ON penta_application.audit_log(application_id);
