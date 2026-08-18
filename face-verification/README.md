# Face Verification Service

Standalone FastAPI service that compares each director's passport photo
against the corporate application's government-ID document, using the
(fixed) face-matching logic in
`../Face_Verification_Test/face_verification_package/`. Kept as its own
service - same reasoning as `../ocr/`: InsightFace/onnxruntime are heavy,
CPU-bound dependencies that don't belong in the main backend's image.

## Endpoint

```
POST /applications/{application_id}/verify-faces
```

Lists `onboarding-applications/{application_id}/` in Storage, downloads
each director's `director_passport_photo/{index}_*` file plus THEIR OWN
`govt_id_*/{index}_*` file, runs `verify_documents()` on each (photo,
government ID) pair independently, and writes one `verification_results`
row per director (`check_type='face_verification'`, `registry_table=NULL`).

A director with a photo but no matching government ID (indexed the same
way) is silently skipped - no result written - rather than reported as a
failure; in the normal wizard flow this shouldn't happen since uploading a
government ID is a mandatory step in each director's block.

## Why "per director against their own government ID," not one big group

Each director uploads their own government ID during their own block in
the wizard (see `OnboardingWizard.jsx`'s `STEP.DIRECTOR_GOVERNMENT_ID`) -
not one shared document for the whole application. Feeding everyone's
photos and IDs into `face_verification`'s multi-document clustering in one
big call would conflate different people's evidence; instead, each
director's photo is compared **only** against that same director's own ID,
one independent pairwise check per director - pairing is done by the
director index embedded in both files' names (see `storage.py`).

An earlier version of this service assumed a single, shared government ID
per application (the wizard used to collect it once, in a separate
corporate-documents step) - under that design, only whichever one director
happened to match the shared ID could ever get a genuine "match," and
every other director was structurally guaranteed to mismatch regardless of
whether their documents were genuine. That's no longer the case.

## Status mapping

| `verify_documents()` status | `verification_results.status` |
|---|---|
| `FACE_CONSISTENT` | `match` |
| `REVIEW_REQUIRED` | `mismatch` |
| `INSUFFICIENT_EVIDENCE` | `error` (a face wasn't detected in one of the two images - not evidence the people differ) |

## Credentials needed to actually run this

- `GOOGLE_APPLICATION_CREDENTIALS` - a GCP/Firebase service account JSON
  with Storage read access to the bucket. The same credential requested
  for the OCR service should work here too (Firebase Storage buckets are
  GCS buckets underneath).
- `FACEVERIFY_DATABASE_URL` - same Postgres connection string as the main
  backend (`backend/.env`'s `DATABASE_URL`). Writes go directly to
  Postgres, not through the Supabase client - see
  `backend/app/onboarding/service.py`'s `receive_wizard_application` for
  why that path was dropped in favor of this one.

## Local dev

```
pip install -r requirements.txt
cp .env.example .env   # fill in the values above
uvicorn faceverify.api:app --reload --port 8002 --app-dir src
```
