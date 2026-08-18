from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from google.cloud import storage

SUBMISSIONS_ROOT = "onboarding-applications"

DIRECTOR_SIGNATURE_SPECIMEN_CATEGORY = "director_signature_specimen"

# Each director uploads their OWN government ID during their block in the
# wizard (see OnboardingWizard.jsx's STEP.DIRECTOR_GOVERNMENT_ID) - not one
# shared document for the whole application. passport/national-ID/voter's-
# card are confirmed (against real samples - see crop.py's
# _SIGNATURE_BOXES) to reliably carry a signature at a known position.
# Driver's license has no calibrated box (no real sample of this system's
# version of that document has been seen) and falls back to
# crop.crop_signature_best_effort's generic heuristic instead.
GOVERNMENT_ID_CATEGORIES = {
    "govt_id_international_passport",
    "govt_id_drivers_license",
    "govt_id_voters_card",
    "govt_id_national_id_card",
}

# Matches how wizardStorage.js names director signature specimen/government-
# ID files: "{directorIndex}_{sanitizedOriginalName}" - identical convention
# to director_passport_photo.
_DIRECTOR_INDEX_RE = re.compile(r"^(\d+)_")


@dataclass
class ApplicationDocuments:
    director_signatures: dict[int, storage.Blob] = field(default_factory=dict)  # director index -> blob
    # director index -> (blob, category) - each director's own government
    # ID, not one shared per application (see GOVERNMENT_ID_CATEGORIES above).
    government_ids: dict[int, tuple[storage.Blob, str]] = field(default_factory=dict)


def list_application_documents(client: storage.Client, bucket_name: str, application_id: str) -> ApplicationDocuments:
    """Scans onboarding-applications/{application_id}/ for the documents
    signature verification cares about - each director's signature
    specimen and their own government ID, both indexed by director. Mirrors
    face-verification/src/faceverify/storage.py exactly."""
    bucket = client.bucket(bucket_name)
    prefix = f"{SUBMISSIONS_ROOT}/{application_id}/"
    result = ApplicationDocuments()

    for blob in client.list_blobs(bucket, prefix=prefix):
        remainder = blob.name[len(prefix):]
        if remainder.endswith("/") or not remainder:
            continue

        parts = remainder.split("/", 1)
        if len(parts) != 2:
            continue
        category, filename = parts

        if category == DIRECTOR_SIGNATURE_SPECIMEN_CATEGORY:
            match = _DIRECTOR_INDEX_RE.match(filename)
            if not match:
                continue
            result.director_signatures[int(match.group(1))] = blob

        elif category in GOVERNMENT_ID_CATEGORIES:
            match = _DIRECTOR_INDEX_RE.match(filename)
            if not match:
                continue
            director_index = int(match.group(1))
            if director_index not in result.government_ids:
                result.government_ids[director_index] = (blob, category)

    return result


def download_to_temp_dir(blobs: dict[str, storage.Blob]) -> Path:
    """Same pattern as faceverify/storage.py's download_to_temp_dir."""
    temp_dir = Path(tempfile.mkdtemp(prefix="sigverify_"))
    for local_name, blob in blobs.items():
        blob.download_to_filename(str(temp_dir / local_name))
    return temp_dir
