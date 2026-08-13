export default function UploadForm({ file, onFileChange, onSubmit, status }) {
  const isUploading = status === "uploading";

  return (
    <div className="upload-card">
      <p>Select a document to upload.</p>
      <input
        type="file"
        onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
        disabled={isUploading}
      />
      <div>
        <button onClick={onSubmit} disabled={!file || isUploading}>
          {isUploading ? "Uploading..." : "Upload"}
        </button>
      </div>
    </div>
  );
}
