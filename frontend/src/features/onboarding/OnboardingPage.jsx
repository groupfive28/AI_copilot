// import { useState } from "react";

// import CorporateAccountForm from "./CorporateAccountForm.jsx";
// import DocumentUploadSection from "./DocumentUploadSection.jsx";
// import { useDocumentUploads } from "./useDocumentUploads.js";
// import { useOnboardingForm } from "./useOnboardingForm.js";
// import { submitApplication } from "./api.js";

// export default function OnboardingPage() {
//   const { fields, errors, setField, validate } = useOnboardingForm();
//   const { uploads, setFile, setSubtype, requiredCategoriesMissing, uploadAll } = useDocumentUploads();

//   const [submitStatus, setSubmitStatus] = useState("idle"); // idle | submitting | done | error
//   const [submitError, setSubmitError] = useState(null);
//   const [result, setResult] = useState(null);

//   async function handleSubmit() {
//     setSubmitError(null);

//     if (!validate()) {
//       setSubmitError("Fix the highlighted fields before submitting.");
//       return;
//     }

//     const missing = requiredCategoriesMissing();
//     if (missing.length > 0) {
//       setSubmitError(`Missing required documents: ${missing.join(", ")}`);
//       return;
//     }

//     setSubmitStatus("submitting");

//     try {
//       const uploadedEntries = await uploadAll();
//       const response = await submitApplication(fields, uploadedEntries);
//       setResult(response);
//       setSubmitStatus("done");
//     } catch (err) {
//       setSubmitError(err.message);
//       setSubmitStatus("error");
//     }
//   }

//   return (
//     <section>
//       <h1>Corporate account opening</h1>
//       <p>Complete the form and upload the required documents to start a new application.</p>

//       <CorporateAccountForm fields={fields} errors={errors} setField={setField} />

//       <DocumentUploadSection uploads={uploads} setFile={setFile} setSubtype={setSubtype} />

//       <button onClick={handleSubmit} disabled={submitStatus === "submitting"}>
//         {submitStatus === "submitting" ? "Submitting..." : "Submit application"}
//       </button>

//       {submitError && <p className="error-text">{submitError}</p>}
//       {submitStatus === "done" && result && <pre className="result">{JSON.stringify(result, null, 2)}</pre>}
//     </section>
//   );
// }


import OnboardingWizard from "./wizard/OnboardingWizard.jsx";

export default function OnboardingPage() {
  return <OnboardingWizard />;
}
