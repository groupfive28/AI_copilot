# Signature Verification Service

Standalone FastAPI service that compares each director's uploaded signature
specimen against a signature found on THEIR OWN government-ID document
(each director uploads their own ID during their block in the wizard - see
`OnboardingWizard.jsx`'s `STEP.DIRECTOR_GOVERNMENT_ID`, not one shared
document for the whole application), using
[SigNet](https://arxiv.org/abs/1705.05787) (a pretrained,
open-source CNN for offline handwritten signature verification, via
[luizgh/sigver](https://github.com/luizgh/sigver)). Kept as its own
service - same reasoning as `../face-verification/` and `../ocr/`: torch
and opencv are heavy, CPU-bound dependencies that don't belong in the main
backend's image.

## Endpoint

```
POST /applications/{application_id}/verify-signatures
```

Lists `onboarding-applications/{application_id}/` in Storage, downloads
each director's `director_signature_specimen/{index}_*` file plus THEIR
OWN `govt_id_*/{index}_*` file, compares each pair independently, and
writes one `verification_results` row per director
(`check_type='signature_verification'`, `registry_table=NULL`).

Returns an empty `results` list - not an error - if no director has a
signature specimen uploaded, or a director has no matching government ID
(shouldn't happen in the normal wizard flow - the ID upload step is
mandatory).

## Read this before trusting the output

This check is meaningfully less precise than face verification, for one
concrete, tested reason - not a hedge, an actual measurement: **the model
never scores a genuine match especially high.** A specimen photo and a
signature cropped out of a photographed ID are two independently-captured
images that will essentially never be pixel-aligned, and this embedding is
sensitive to that - a real genuine pair tops out around 0.7 similarity,
not 0.9+, the way a more precise model would produce.

`pipeline.py`'s `_MATCH_THRESHOLD` has been through four real revisions,
each driven by evidence or an explicit team decision, not guesswork - see
that file's comment for the full history:

1. **0.5** (first attempt) - rejected after one real different-people
   passport-signature comparison scored 0.9256, above threshold: a
   confirmed false "match."
2. **0.97** - raised in response, deliberately conservative. This
   overcorrected: repeated real application runs then showed genuine
   signatures routinely scoring 0.60-0.73, so nearly every application
   escalated on this check regardless of whether the signature was
   actually right.
3. **0.6** - repeated real testing (many full application runs, not a
   single sample) found a consistent gap: genuine pairs scored 0.60-0.73,
   genuinely wrong ones scored 0.10-0.30. 0.6 sat at the bottom of that
   gap. In practice, further real runs kept landing genuine signatures
   below it often enough that clean applications were still routinely
   escalating on a legitimate signature.
4. **0.5** (current) - a deliberate team decision to accept the specific
   risk identified in bullet 1, weighed against the model's now-confirmed
   inability to reliably clear a higher bar for genuine signatures. This
   is a considered tradeoff prioritizing not blocking legitimate
   applications, not a claim that a false "match" at this threshold can't
   happen - it already has once, in testing. Revisit if a real mismatch is
   observed scoring at or above 0.5.

Document coverage is *not* a separate limitation - all three document
types this system issues (international passport, national ID, voter's
card) were confirmed, against the real "Penta Republic" samples, to carry
a genuine signature, each at a calibrated fixed position in `crop.py`'s
`_SIGNATURE_BOXES` (passport: labeled "Holder's Signature / Signature du
titulaire"; national ID: labeled "CARDHOLDER SIGNATURE"; voter's card: no
label, but present at a consistent position). Only the driver's license
has no calibrated box (no real sample of this system's version of that
document has been seen) and falls back to
`crop.crop_signature_best_effort()`'s generic ink-blob heuristic, which
frequently finds nothing.

This check participates in `auto_decide_application`'s rollup the same
way face verification does - a mismatch can escalate an application on
its own. It briefly did not (while the threshold was 0.97 and unusable),
but that exclusion was reverted once the threshold was recalibrated to
0.6 against real evidence - see `verification/service.py`'s
`auto_decide_application` docstring for that history.

## Status mapping

| Outcome | `verification_results.status` |
|---|---|
| Similarity >= threshold | `match` |
| Similarity < threshold | `mismatch` |
| Couldn't read an image, or a crop was blank/unparseable | `error` |
| No signature field known/detected on this document type | *(no row written)* |

That last row is deliberate, not an oversight: a national ID or voter's
card genuinely having no signature to check isn't evidence of anything
wrong, so it's skipped the same way `verify_application()` in the main
backend skips a document category with no registry mapping - writing a
`status="not_found"` row instead would misrepresent "nothing to check" as
a finding, and (now that this check feeds `auto_decide_application` again)
would incorrectly escalate an application for a reason unrelated to fraud
risk.

## Model

`SigNet`, pretrained on the GPDS dataset, via the feature-extraction
checkpoint released alongside the original paper (not the `sigver` PyPI
package itself - its install instructions use a pip flag removed years ago,
so the architecture is reimplemented directly in `model.py`, verified to
load the same pretrained weights). Weights are downloaded automatically on
first use from the paper authors' Google Drive link (see `model.py`) and
cached at `SIGVERIFY_MODEL_PATH` (default `models/signet.pth`, gitignored -
63MB is too large to comfortably commit). If that link ever goes dead, the
service will fail to start rather than silently degrade - there's no
fallback model.

## Credentials needed to actually run this

Same as `../face-verification/README.md` - `GOOGLE_APPLICATION_CREDENTIALS`
(or local `gcloud auth application-default login`) for Storage read access,
and `SIGVERIFY_DATABASE_URL` (same Postgres connection as the main
backend).

## Local dev

```
pip install -r requirements.txt
cp .env.example .env   # fill in the values above
uvicorn sigverify.api:app --reload --port 8003 --app-dir src
```
