import { DOCUMENT_CATEGORIES } from "./constants.js";
import DocumentUploadSlot from "./DocumentUploadSlot.jsx";

export default function DocumentUploadSection({ uploads, setFile, setSubtype }) {
  return (
    <div className="form-card">
      <h2>Required documents</h2>
      <p>Accepted formats: JPG, PNG, WEBP, PDF.</p>

      {DOCUMENT_CATEGORIES.map((category) => (
        <DocumentUploadSlot
          key={category.id}
          category={category}
          entry={uploads[category.id]}
          onFileChange={setFile}
          onSubtypeChange={setSubtype}
        />
      ))}
    </div>
  );
}
