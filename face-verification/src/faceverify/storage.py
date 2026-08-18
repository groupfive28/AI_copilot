from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from google.cloud import storage

SUBMISSIONS_ROOT = "onboarding-applications"

DIRECTOR_PASSPORT_PHOTO_CATEGORY = "director_passport_photo"

# Each director uploads their OWN government ID during their block in the
# wizard (see OnboardingWizard.jsx's STEP.DIRECTOR_GOVERNMENT_ID) - not one
# shared document for the whole application anymore. The filename still
# embeds the director index (uploadDirectorGovernmentId in wizardStorage.js),
# same convention as director_passport_photo, so which director an ID
# belongs to is recovered the same way. A director could in principle use
# a different ID type than another (one passport, one voter's card), so
# every category below is scanned, not just one.
GOVERNMENT_ID_CATEGORIES = {
    "govt_id_international_passport",
    "govt_id_drivers_license",
    "govt_id_voters_card",
    "govt_id_national_id_card",
}

# Matches how wizardStorage.js names director photo/government-ID files:
# "{directorIndex}_{sanitizedOriginalName}".
_DIRECTOR_INDEX_RE = re.compile(r"^(\d+)_")


@dataclass
class ApplicationDocuments:
    director_photos: dict[int, storage.Blob] = field(default_factory=dict)  # director index -> blob
    # director index -> (blob, category) - each director's own government ID,
    # not one shared per application (see GOVERNMENT_ID_CATEGORIES above).
    government_ids: dict[int, tuple[storage.Blob, str]] = field(default_factory=dict)


def list_application_documents(client: storage.Client, bucket_name: str, application_id: str) -> ApplicationDocuments:
    """
    Scans onboarding-applications/{application_id}/ and picks out exactly
    the documents face verification cares about - director passport photos
    and each director's own government ID, both indexed by director. If two
    files somehow land under the same director index and category (shouldn't
    happen per the wizard's UI, but Storage doesn't enforce that), the first
    one found wins rather than silently taking a "last write wins" one.
    Everything else under the application (proof of address, TIN
    certificate, etc.) has no face to compare and is ignored here.
    """
    bucket = client.bucket(bucket_name)
    prefix = f"{SUBMISSIONS_ROOT}/{application_id}/"
    result = ApplicationDocuments()

    for blob in client.list_blobs(bucket, prefix=prefix):
        remainder = blob.name[len(prefix) :]
        if remainder.endswith("/") or not remainder:
            continue  # folder placeholder

        parts = remainder.split("/", 1)
        if len(parts) != 2:
            continue  # not nested under a category folder
        category, filename = parts

        if category == DIRECTOR_PASSPORT_PHOTO_CATEGORY:
            match = _DIRECTOR_INDEX_RE.match(filename)
            if not match:
                continue  # unexpected filename shape - skip rather than guess which director
            result.director_photos[int(match.group(1))] = blob

        elif category in GOVERNMENT_ID_CATEGORIES:
            match = _DIRECTOR_INDEX_RE.match(filename)
            if not match:
                continue
            director_index = int(match.group(1))
            if director_index not in result.government_ids:
                result.government_ids[director_index] = (blob, category)

    return result


def download_to_temp_dir(blobs: dict[str, storage.Blob]) -> Path:
    """
    Downloads each blob to a temp directory under the given local filename,
    for verify_documents() (which reads a local folder, not cloud storage
    references - see face_verification/verifier.py:_read_documents).
    Caller is responsible for cleaning up the returned directory.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="faceverify_"))
    for local_name, blob in blobs.items():
        blob.download_to_filename(str(temp_dir / local_name))
    return temp_dir
