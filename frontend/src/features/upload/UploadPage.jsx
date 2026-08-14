import UploadForm from "./UploadForm.jsx";
import { useUpload } from "./useUpload.js";

export default function UploadPage() {
  const { file, setFile, status, result, error, submit } = useUpload();

  return (
    <section>
      <h1>Upload a document</h1>
      <p>
        Prototype scaffolding: the backend accepts the file and returns its metadata only. No
        OCR, extraction, or verification happens yet.
      </p>

      <UploadForm file={file} onFileChange={setFile} onSubmit={submit} status={status} />

      {status === "done" && result && <pre className="result">{JSON.stringify(result, null, 2)}</pre>}
      {status === "error" && <p className="error-text">{error}</p>}
    </section>
  );
}
