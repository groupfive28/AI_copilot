import { getDownloadURL, ref, uploadBytes } from "firebase/storage";

import { ensureAnonymousAuth, storage } from "../../../shared/firebase/client.js";

function sanitizeFileName(name) {
  return name.replace(/[^a-zA-Z0-9.\-_]/g, "_");
}

/**
 * Paths are flat - onboarding-applications/{applicationId}/{category}/{filename} -
 * because that's exactly what the OCR service's list_submitted_documents()
 * expects (ocr/src/penta/ingest.py): it splits each blob name on the first
 * "/" after the application id to get (document_category, filename), so
 * anything nested deeper than that is invisible to it. draftId here IS the
 * eventual application_id - generated client-side up front and passed
 * through to POST /wizard-submit unchanged (see OnboardingWizard.jsx),
 * instead of the backend minting a fresh one that wouldn't match where
 * these files actually landed.
 */

/**
 * @param {File} file
 * @param {string} draftId - becomes this application's id
 * @param {number} directorIndex - embedded in the filename (not the path -
 *   see module note above) so multiple directors' photos don't collide
 *   under the one category.
 */
export async function uploadDirectorPassportPhoto(file, draftId, directorIndex) {
  const user = await ensureAnonymousAuth();

  const storagePath = `onboarding-applications/${draftId}/director_passport_photo/${directorIndex}_${sanitizeFileName(file.name)}`;
  const storageRef = ref(storage, storagePath);

  await uploadBytes(storageRef, file, {
    contentType: file.type || undefined,
    customMetadata: {
      draftId,
      directorIndex: String(directorIndex),
      category: "director_passport_photo",
      originalFileName: file.name,
      uploadedBy: user.uid,
      uploadedAt: new Date().toISOString(),
    },
  });

  const downloadUrl = await getDownloadURL(storageRef);
  return { storagePath, downloadUrl };
}

/**
 * @param {File} file
 * @param {string} draftId - becomes this application's id
 * @param {number} directorIndex - same convention as uploadDirectorPassportPhoto,
 *   embedded in the filename so multiple directors' specimens don't
 *   collide under the one category.
 */
export async function uploadDirectorSignatureSpecimen(file, draftId, directorIndex) {
  const user = await ensureAnonymousAuth();

  const storagePath = `onboarding-applications/${draftId}/director_signature_specimen/${directorIndex}_${sanitizeFileName(file.name)}`;
  const storageRef = ref(storage, storagePath);

  await uploadBytes(storageRef, file, {
    contentType: file.type || undefined,
    customMetadata: {
      draftId,
      directorIndex: String(directorIndex),
      category: "director_signature_specimen",
      originalFileName: file.name,
      uploadedBy: user.uid,
      uploadedAt: new Date().toISOString(),
    },
  });

  const downloadUrl = await getDownloadURL(storageRef);
  return { storagePath, downloadUrl };
}

/**
 * @param {File} file
 * @param {string} draftId - becomes this application's id
 * @param {number} directorIndex - same convention as uploadDirectorPassportPhoto/
 *   uploadDirectorSignatureSpecimen - embedded in the filename so each
 *   director's own ID document is distinguishable, letting face-verification/
 *   signature-verification match each director against their own ID instead
 *   of a single shared one.
 * @param {string} category - one of DIRECTOR_GOVERNMENT_ID_TYPES's ids in
 *   constants.js (govt_id_international_passport/govt_id_drivers_license/
 *   govt_id_voters_card/govt_id_national_id_card) - still the folder name,
 *   same categories as before this was per-director, just no longer shared.
 */
export async function uploadDirectorGovernmentId(file, draftId, directorIndex, category) {
  const user = await ensureAnonymousAuth();

  const storagePath = `onboarding-applications/${draftId}/${category}/${directorIndex}_${sanitizeFileName(file.name)}`;
  const storageRef = ref(storage, storagePath);

  await uploadBytes(storageRef, file, {
    contentType: file.type || undefined,
    customMetadata: {
      draftId,
      directorIndex: String(directorIndex),
      category,
      originalFileName: file.name,
      uploadedBy: user.uid,
      uploadedAt: new Date().toISOString(),
    },
  });

  const downloadUrl = await getDownloadURL(storageRef);
  return { storagePath, downloadUrl };
}

/**
 * @param {File} file
 * @param {string} category - id from CORPORATE_DOCUMENT_TYPES in constants.js
 * @param {string} draftId - becomes this application's id
 */
export async function uploadCorporateDocument(file, category, draftId) {
  const user = await ensureAnonymousAuth();

  const storagePath = `onboarding-applications/${draftId}/${category}/${sanitizeFileName(file.name)}`;
  const storageRef = ref(storage, storagePath);

  await uploadBytes(storageRef, file, {
    contentType: file.type || undefined,
    customMetadata: {
      draftId,
      category,
      originalFileName: file.name,
      uploadedBy: user.uid,
      uploadedAt: new Date().toISOString(),
    },
  });

  const downloadUrl = await getDownloadURL(storageRef);
  return { storagePath, downloadUrl };
}
