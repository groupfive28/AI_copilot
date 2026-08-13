import { API_BASE_URL } from "../../shared/api/client.js";

/**
 * Posts a file to the document-processing layer. Uses raw fetch (not
 * apiRequest) because this is a multipart/form-data upload, not JSON.
 */
export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/v1/document-processing/documents`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Upload failed (${response.status}): ${detail}`);
  }

  return response.json();
}
