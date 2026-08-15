# Face Verification Service

Age-aware face matching between a director's recent passport photograph and
**any number** of their uploaded documents that might contain a face (NIN,
Voter's Card, Passport, Driver's Licence — documents like the CAC
certificate, utility bill, or board resolution are automatically skipped
since they carry no face). Built to slot into an existing KYC pipeline:
called after the NIN/BVN cross-check step succeeds, and writes its result
to Supabase for the admin portal to consume.

## What it does

1. Reads the director's Firestore record to get the **recent photo URL**
   and the **list of document URLs** (any mix of JPG/JPEG/PNG — format is
   read from file content, not the URL/extension, so this is fully
   format-agnostic).
2. Downloads each by simple HTTP GET (no Firebase Storage SDK needed).
3. Runs face detection + quality checks on every image. Documents with no
   detectable face (utility bill, CAC cert, etc.) are **skipped**, not
   penalised.
4. For every document that does have a face, computes ArcFace similarity
   against the recent photo, estimates the age gap (using a verified DOB
   if available), and produces a per-document verdict.
5. **Aggregates** all per-document verdicts into one overall result:
   - Any document MISMATCH → overall `NEEDS_REVIEW` (inconsistency is a
     signal for a human, not an auto-reject)
   - At least one MATCHED, none mismatched → overall `MATCHED`
   - Nothing matched, nothing mismatched → `NEEDS_REVIEW`
   - No document had a detectable face at all → `NEEDS_REVIEW`
6. Writes `director_id`, `overall_result`, `reasons`, per-document
   breakdown, and best similarity score to **Supabase** (your
   verification portal reads from here), and optionally mirrors to
   Firestore for local audit.

## Files

| File | Purpose |
|---|---|
| `config.py` | All tunable settings: thresholds, Firestore field names, Supabase settings |
| `firebase_client.py` | Reads Firestore, downloads documents by URL |
| `supabase_client.py` | Writes the aggregated result to Supabase |
| `face_processing.py` | Detection, alignment, quality gating (InsightFace) |
| `embedding.py` | Cosine similarity |
| `age_estimation.py` | Age-gap estimation, banding, and estimate-disagreement flagging |
| `decision_engine.py` | Per-document threshold logic + multi-document aggregation |
| `verification_service.py` | Orchestrator — the main entry point |
| `api.py` | FastAPI HTTP wrapper |
| `tests/test_local_pipeline.py` | Run the pipeline on local files, no Firebase/Supabase needed |

## Setup

```bash
pip install -r requirements.txt
```

On first run, InsightFace downloads its `buffalo_l` model pack (~280MB,
one-time) from the official model zoo. No manual download needed.

### Environment variables

```bash
export FIREBASE_CREDENTIALS_PATH=/secrets/firebase-service-account.json
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_KEY=your-service-role-key       # service_role, NOT anon key
export SUPABASE_RESULTS_TABLE=face_verification_results   # optional, this is the default
```

### Firestore schema this expects

On each director document (`directors/{director_id}`):

```json
{
  "recentPhotoURL": "https://firebasestorage.googleapis.com/.../recent_photo.jpg?...",
  "documentURLs": [
    { "type": "NIN", "url": "https://.../nin.png" },
    { "type": "VOTERS_CARD", "url": "https://.../voters_card.jpeg" },
    { "type": "CAC_CERTIFICATE", "url": "https://.../cac.jpg" },
    { "type": "UTILITY_BILL", "url": "https://.../utility_bill.jpg" }
  ],
  "dateOfBirth": "2002-10-24"
}
```

`documentURLs` can also just be a flat list of plain URL strings (no
`type` label) — the service handles both shapes; the label is only used
for nicer reporting, matching still runs on every document either way.

`dateOfBirth` should be the value already confirmed by your NIN/BVN
cross-check step — this is what makes age-gap estimation reliable rather
than guessed purely from the photos.

Field names (`recentPhotoURL`, `documentURLs`, `dateOfBirth`) are set in
`config.py` under `FIELD_RECENT_PHOTO_URL` / `FIELD_DOCUMENT_URLS` /
`FIELD_DATE_OF_BIRTH` — change them there if your actual schema uses
different names.

### Supabase table this writes to

```sql
create table face_verification_results (
    id              uuid primary key default gen_random_uuid(),
    director_id     text not null,
    overall_result  text not null,          -- MATCHED | MISMATCH | NEEDS_REVIEW
    best_similarity_score  float,
    documents_checked      jsonb not null,  -- full per-document breakdown, for portal drill-down
    reasons                jsonb,
    created_at      timestamptz not null default now()
);

create unique index if not exists face_verification_results_director_id_key
    on face_verification_results (director_id);
```

The unique index means re-running verification for the same director
upserts (overwrites) their row rather than creating duplicates — adjust
if you'd rather keep a full history of every verification attempt (drop
the unique index, switch the client from `upsert` to `insert` in
`supabase_client.py`).

## Running locally (no Firebase/Supabase, for dev/demo)

Takes one anchor photo and **any number** of candidate documents:

```bash
python tests/test_local_pipeline.py \
    --recent recent.jpg \
    --documents nin.jpg voters_card.png passport.jpeg \
    --dob 2002-10-24
```

Works with a single document too:

```bash
python tests/test_local_pipeline.py --recent recent.jpg --documents id_document.jpg
```

This is the fastest way to test against your dummy-country sample
documents before wiring up Firestore/Supabase.

## Running as a service

```bash
uvicorn api:app --host 0.0.0.0 --port 8001
```

Your main backend then calls:

```
POST /verify/{director_id}
```

which fetches everything by URL, runs the full pipeline, writes to
Supabase, and returns the same result synchronously. For production
volume, put this behind a queue/worker rather than calling inline from a
request thread — face detection + embedding is CPU-bound and takes
roughly 200-500ms per image on CPU.

## Calibration — the part you should not skip

The thresholds in `config.AGE_GAP_THRESHOLDS` are reasonable *starting
points* based on published ArcFace behavior, not numbers validated against
your specific document set. Before going live:

1. Build a labeled validation set — pairs of (recent photo, document
   photo) with known ground truth (same-person / different-person) across
   a range of age gaps and document types. Public aging datasets like
   **FG-NET** or **CACD** are useful for the pure age-gap dimension; your
   own dummy-country documents are the right source for the
   document-quality dimension (printed-and-rescanned photos genuinely
   score lower even for a true match, as testing already showed).
2. Run batches through `tests/test_local_pipeline.py` (or a small script
   built on `verification_service.py`'s internals) and record the
   similarity scores.
3. Plot same-person vs. different-person similarity distributions, split
   by age-gap band, and adjust `match_threshold` / `review_threshold` per
   band so your false-accept and false-reject rates land where your risk
   appetite wants them. Bank KYC generally biases toward a wider
   `NEEDS_REVIEW` band and a low false-accept rate — false accepts are the
   costly failure mode, not false reviews.
4. Re-calibrate periodically as you accumulate real outcome data.

## Known limitations

- **Large age gaps (child photo → adult) are the weakest case for any
  face-matching model**, including ArcFace. Testing also surfaced that the
  model's own age *estimate* can be badly wrong on child photos (e.g.
  guessing a 10-year-old is 25) — `age_estimation.py` now flags this
  disagreement explicitly (`estimate_disagreement_flag`) whenever it's
  detected, and this shows up in a document's `reasons`. Always pass a
  verified `dateOfBirth` in production; don't rely on the model's own age
  guess as the primary signal.
- **A document with a mismatched face does not auto-reject the
  application** by design — it routes to `NEEDS_REVIEW` so a human can
  distinguish "one bad-quality scan" from "an actual swapped identity."
  If your risk policy wants a harder auto-reject on any mismatch, that's
  a one-line change in `decision_engine.aggregate_multi_document_decision`.
- The yaw/pose estimate in `face_processing._estimate_yaw` is a coarse
  heuristic from 5-point landmarks, not a calibrated head-pose model. Fine
  for a quality gate; don't treat its output as a precise angle.
- CPU inference is used by default (`INSIGHTFACE_PROVIDERS` in
  `config.py`). Switch to `CUDAExecutionProvider` if you have GPU capacity
  and need higher throughput.
- `download_from_url` retries transient network failures
  (`HTTP_MAX_RETRIES`, default 2) but doesn't handle authentication —
  if your Firebase Storage URLs require an auth token/signed URL that
  expires quickly, make sure the database side regenerates URLs shortly
  before triggering verification, not far in advance.
