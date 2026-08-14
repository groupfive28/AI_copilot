export default function DocumentUploadSlot({ category, entry, onFileChange, onSubtypeChange }) {
  const { file, status, error } = entry;

  return (
    <div className="upload-slot">
      <div className="upload-slot-header">
        <span>{category.label}</span>
        <span className={`upload-status upload-status-${status}`}>{status}</span>
      </div>

      {category.hasSubtype && (
        <select
          value={entry.subtype ?? ""}
          onChange={(e) => onSubtypeChange(category.id, e.target.value)}
          disabled={status === "uploading"}
        >
          <option value="">Select document type</option>
          {category.subtypeOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}

      <input
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.pdf"
        onChange={(e) => onFileChange(category.id, e.target.files?.[0] ?? null)}
        disabled={status === "uploading"}
      />

      {file && <span className="upload-filename">{file.name}</span>}
      {error && <span className="field-error">{error}</span>}
    </div>
  );
}
