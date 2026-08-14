import { useState } from "react";

import { DOCUMENT_CATEGORIES } from "./constants.js";
import { uploadDocument } from "./storage.js";

function initialUploads() {
  const entries = {};
  for (const category of DOCUMENT_CATEGORIES) {
    entries[category.id] = { file: null, subtype: null, status: "idle", error: null, reference: null };
  }
  return entries;
}

export function useDocumentUploads() {
  const [uploads, setUploads] = useState(initialUploads);
  // Groups this submission's documents in Storage before the backend has
  // assigned a real application reference (that only happens after upload).
  const [draftId] = useState(() => crypto.randomUUID());

  function setFile(categoryId, file) {
    setUploads((prev) => ({
      ...prev,
      [categoryId]: { ...prev[categoryId], file, status: "idle", error: null, reference: null },
    }));
  }

  function setSubtype(categoryId, subtype) {
    setUploads((prev) => ({
      ...prev,
      [categoryId]: { ...prev[categoryId], subtype },
    }));
  }

  function requiredCategoriesMissing() {
    return DOCUMENT_CATEGORIES.filter((category) => !uploads[category.id].file).map((category) => category.label);
  }

  /** Uploads every selected file to storage.js's uploadDocument(), sequentially. */
  async function uploadAll() {
    const results = {};

    for (const category of DOCUMENT_CATEGORIES) {
      const entry = uploads[category.id];
      if (!entry.file) continue;

      setUploads((prev) => ({
        ...prev,
        [category.id]: { ...prev[category.id], status: "uploading", error: null },
      }));

      try {
        const reference = await uploadDocument(entry.file, category.id, draftId);
        setUploads((prev) => ({
          ...prev,
          [category.id]: { ...prev[category.id], status: "done", reference },
        }));
        results[category.id] = { ...entry, reference };
      } catch (err) {
        setUploads((prev) => ({
          ...prev,
          [category.id]: { ...prev[category.id], status: "error", error: err.message },
        }));
        throw err;
      }
    }

    return results;
  }

  return { uploads, setFile, setSubtype, requiredCategoriesMissing, uploadAll };
}
