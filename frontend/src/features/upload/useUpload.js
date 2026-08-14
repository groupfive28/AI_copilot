import { useState } from "react";

import { uploadDocument } from "./api.js";

/**
 * Local upload state machine for the upload feature. No OCR/extraction/
 * verification logic — just tracks the request and hands back whatever
 * metadata the backend echoes.
 */
export function useUpload() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | uploading | done | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function submit() {
    if (!file) return;
    setStatus("uploading");
    setError(null);

    try {
      const data = await uploadDocument(file);
      setResult(data);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  function reset() {
    setFile(null);
    setStatus("idle");
    setResult(null);
    setError(null);
  }

  return { file, setFile, status, result, error, submit, reset };
}
