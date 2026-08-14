import { getDownloadURL, ref, uploadBytes } from "firebase/storage";

import { ensureAnonymousAuth, storage } from "../../../shared/firebase/client.js";

function sanitizeFileName(name) {
  return name.replace(/[^a-zA-Z0-9.\-_]/g, "_");
}

/**
 * @param {File} file
 * @param {string} draftId - groups everything from one in-progress wizard
 *   session, since there's no application reference yet.
 * @param {number} directorIndex - this director's position in the list,
 *   so each director's photo lands in its own folder.
 */
export async function uploadDirectorPassportPhoto(file, draftId, directorIndex) {
  const user = await ensureAnonymousAuth();

  const storagePath = `onboarding-wizard/${draftId}/directors/${directorIndex}/passport_photo/${sanitizeFileName(file.name)}`;
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
 * @param {string} category - id from CORPORATE_DOCUMENT_TYPES in constants.js
 * @param {string} draftId
 */
export async function uploadCorporateDocument(file, category, draftId) {
  const user = await ensureAnonymousAuth();

  const storagePath = `onboarding-wizard/${draftId}/corporate-documents/${category}/${sanitizeFileName(file.name)}`;
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