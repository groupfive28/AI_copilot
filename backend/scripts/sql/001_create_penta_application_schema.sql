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
    -- Free-text, collected in the wizard's dedicated address step (not
    -- part of the older non-wizard ApplicationSubmission) - checked
    -- against pedco_electricity_registry.address for the matched company,
    -- fuzzily (substring, not exact match - see
    -- app/verification/service.py's _address_matches) since a person
    -- typing a full address rarely matches a registry's terse format
    -- exactly.
    company_address              TEXT,
    status                      TEXT NOT NULL DEFAULT 'received'
        CONSTRAINT applications_status_valid
        CHECK (status IN ('received', 'processing', 'escalated', 'approved', 'rejected')),
    -- Granular sub-state of the background pipeline (run_post_submission_pipeline),
    -- separate from status - NULL until the pipeline starts running, 'done'
    -- once it finishes regardless of what status it lands on. Lets the
    -- dashboard show "currently extracting documents" instead of just
    -- "processing" with no indication of what's actually happening.
    pipeline_stage               TEXT
        CONSTRAINT applications_pipeline_stage_valid
        CHECK (pipeline_stage IS NULL OR pipeline_stage IN ('extracting', 'verifying_faces', 'verifying_signatures', 'checking_registries', 'done')),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per director submitted through the wizard, in submission order
-- (director_index is 0-based, matching the index embedded in that
-- director's Storage filenames - see wizardStorage.js). Captures the
-- registry-matched name at submission time (NULL if the NIN didn't match
-- anything - see receive_wizard_application) so later review screens can
-- label a director's documents/checks by name instead of just an opaque
-- index number. Written once at submission, never updated.
CREATE TABLE penta_application.application_directors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id      UUID NOT NULL REFERENCES penta_application.applications(id),
    director_index      INT NOT NULL,
    nin                 TEXT NOT NULL,
    first_name          TEXT,
    middle_name         TEXT,
    last_name           TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT application_directors_unique_index UNIQUE (application_id, director_index)
);

CREATE INDEX application_directors_application_id_idx ON penta_application.application_directors(application_id);

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
        CHECK (check_type IN ('registry_lookup', 'face_verification', 'signature_verification')),
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
                'cac_tin_registry',
                'pedco_electricity_registry'
            )
        ),
    status               TEXT NOT NULL
        CONSTRAINT verification_results_status_valid
        CHECK (status IN ('match', 'mismatch', 'not_found', 'error')),
    discrepancy_details   JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT verification_results_registry_table_required
        CHECK (
            (check_type = 'registry_lookup'         AND registry_table IS NOT NULL) OR
            (check_type = 'face_verification'       AND registry_table IS NULL) OR
            (check_type = 'signature_verification'  AND registry_table IS NULL)
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
