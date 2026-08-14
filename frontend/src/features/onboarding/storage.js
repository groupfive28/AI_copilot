// Uploads documents directly from the browser to Firebase Storage, using the
// client SDK (chosen over routing through our backend - prototype, moving
// fast). Storage rules require an authenticated request, and this app has
// no real login flow yet, so we sign in anonymously first - see
// ensureAnonymousAuth() in shared/firebase/client.js.
import { getDownloadURL, ref, uploadBytes } from "firebase/storage";

import { ensureAnonymousAuth, storage } from "../../shared/firebase/client.js";

function sanitizeFileName(name) {
  return name.replace(/[^a-zA-Z0-9.\-_]/g, "_");
}

/**
 * @param {File} file
 * @param {string} category - one of DOCUMENT_CATEGORIES ids from constants.js
 * @param {string} draftId - groups all documents from one in-progress
 *   application submission together, since the backend only assigns a real
 *   application reference after all uploads finish.
 * @returns {Promise<{ storagePath: string, downloadUrl: string }>}
 */
export async function uploadDocument(file, category, draftId) {
  await ensureAnonymousAuth();

  const storagePath = `onboarding-applications/${draftId}/${category}/${sanitizeFileName(file.name)}`;
  const storageRef = ref(storage, storagePath);

  await uploadBytes(storageRef, file, { contentType: file.type || undefined });
  const downloadUrl = await getDownloadURL(storageRef);

  return { storagePath, downloadUrl };
}
