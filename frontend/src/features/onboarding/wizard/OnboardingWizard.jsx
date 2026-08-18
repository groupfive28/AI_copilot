import { useState } from "react";
import { supabase } from "../../../shared/supabase/client.js";
import { CORPORATE_DOCUMENT_TYPES, DIRECTOR_GOVERNMENT_ID_TYPES } from "../constants.js";
import { submitCorporateWizardApplication } from "../api.js";
import {
  uploadCorporateDocument,
  uploadDirectorGovernmentId,
  uploadDirectorPassportPhoto,
  uploadDirectorSignatureSpecimen,
} from "./wizardStorage.js";
import MoneyLoader from "./MoneyLoader.jsx";
import "./onboardingWizard.css";

// ---------------------------------------------------------------------------
// Table / column names — adjust these to match your actual Supabase schema
// if any of them differ from what's assumed here.
// ---------------------------------------------------------------------------
const CAC_TABLE = "cac_tin_registry";
const CAC_NUMBER_COLUMN = "RC_number"; // the "CAC number" field, called RC-number in Supabase
const TIN_COLUMN = "TIN";
const COMPANY_NAME_COLUMN = "company_name";

const NIN_TABLE = "nin_registry";
const NIN_COLUMN = "nin_id";
// "D.O.B" is the real column name (literal dots) - aliased back to
// date_of_birth so the rest of this component can keep reading
// currentDirector.date_of_birth without knowing about the alias.
const NIN_FIELDS = 'first_name,middle_name,last_name,email,phone_number,date_of_birth:"D.O.B"';

const BVN_TABLE = "bvn_registry";
const BVN_COLUMN = "bvn_id";
const BVN_FIELDS = "first_name,last_name,middle_name";

const MAX_REJECTIONS = 3; // "take me back" clicks allowed before block

// Corporate account opening requires at least 2 directors, per team decision.
const MIN_DIRECTORS = 2;

const STEP = {
  CAC: "cac",
  CONFIRM_COMPANY: "confirm_company",
  BLOCKED: "blocked",
  TIN: "tin",
  DIRECTORS: "directors",
  DIRECTOR_NIN: "director_nin",
  DIRECTOR_NIN_CONFIRM: "director_nin_confirm",
  DIRECTOR_BVN: "director_bvn",
  DIRECTOR_PASSPORT_PHOTO: "director_passport_photo",
  // Compared against a signature found on this director's OWN government-ID
  // document (uploaded next, in DIRECTOR_GOVERNMENT_ID) by
  // signature-verification/ - see that service's README for how reliable
  // this check actually is (short version: low-confidence even for a
  // genuine match, given realistic capture variance).
  DIRECTOR_SIGNATURE: "director_signature",
  // This director's own government ID - compared against THEIR OWN photo/
  // signature (not a shared, application-wide document) by
  // face-verification/ and signature-verification/.
  DIRECTOR_GOVERNMENT_ID: "director_government_id",
  // Company-level steps, once for the whole application (not per director) -
  // inserted after the directors list is complete. company_address, the
  // utility bill/CAC certificate, and the CAC status report are AI-verified
  // (see backend/app/verification/service.py); board resolution is
  // collected but deliberately not verified yet.
  COMPANY_ADDRESS: "company_address",
  UTILITY_BILL: "utility_bill",
  CAC_CERTIFICATE_UPLOAD: "cac_certificate_upload",
  BOARD_RESOLUTION: "board_resolution",
  STATUS_REPORT: "status_report",
  CORPORATE_DOCUMENTS: "corporate_documents",
  COMING_SOON: "coming_soon",
};

function namesMatch(a, b) {
  return (a ?? "").trim().toLowerCase() === (b ?? "").trim().toLowerCase();
}

function initials(first, last) {
  return `${(first ?? "").charAt(0)}${(last ?? "").charAt(0)}`.toUpperCase();
}

function CompanyHeader({ companyName }) {
  if (!companyName) return null;
  return (
    <div className="ow-company-header">
      <span>{companyName}</span>
    </div>
  );
}

export default function OnboardingWizard() {
  const [step, setStep] = useState(STEP.CAC);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState(null);
  const [submissionResult, setSubmissionResult] = useState(null);

  // Groups every upload from this wizard session together in Storage,
  // since there's no real application reference until submission.
  const [draftId] = useState(() => crypto.randomUUID());

  const [cacNumber, setCacNumber] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [rejectionCount, setRejectionCount] = useState(0);

  const [tin, setTin] = useState("");

  const [directors, setDirectors] = useState([]);
  const [ninInput, setNinInput] = useState("");
  const [bvnInput, setBvnInput] = useState("");
  const [currentDirector, setCurrentDirector] = useState(null); // prefilled NIN + BVN data mid-flow
  const [passportPhotoFile, setPassportPhotoFile] = useState(null);
  const [signatureFile, setSignatureFile] = useState(null);
  const [governmentIdCategory, setGovernmentIdCategory] = useState("");
  const [governmentIdFile, setGovernmentIdFile] = useState(null);

  // Company-level - collected once, after all directors are added.
  const [companyAddress, setCompanyAddress] = useState("");
  const [utilityBillFile, setUtilityBillFile] = useState(null);
  const [cacCertificateFile, setCacCertificateFile] = useState(null);
  const [boardResolutionFile, setBoardResolutionFile] = useState(null);
  const [statusReportFile, setStatusReportFile] = useState(null);

  const [corporateDocs, setCorporateDocs] = useState([]);
  const [corpDocCategory, setCorpDocCategory] = useState("");
  const [corpDocFile, setCorpDocFile] = useState(null);
  // Bumped to force the file <input> to remount, so clearing the selection
  // also clears the filename it displays - React won't do that just from
  // corpDocFile being reset to null, since file inputs are uncontrolled.
  const [corpDocFileInputKey, setCorpDocFileInputKey] = useState(0);

  function handleClearCorpDocSelection() {
    setCorpDocCategory("");
    setCorpDocFile(null);
    setCorpDocFileInputKey((key) => key + 1);
    setError(null);
  }

  async function withLoading(message, fn) {
    setError(null);
    setLoading(true);
    setLoadingMessage(message);
    try {
      await fn();
    } finally {
      setLoading(false);
    }
  }

  // --- Cancel: reset the entire wizard back to the start ------------------
  function handleWizardCancel() {
    setStep(STEP.CAC);
    setError(null);
    setCacNumber("");
    setCompanyName("");
    setRejectionCount(0);
    setTin("");
    setDirectors([]);
    setNinInput("");
    setBvnInput("");
    setCurrentDirector(null);
    setPassportPhotoFile(null);
    setSignatureFile(null);
    setGovernmentIdCategory("");
    setGovernmentIdFile(null);
    setCompanyAddress("");
    setUtilityBillFile(null);
    setCacCertificateFile(null);
    setBoardResolutionFile(null);
    setStatusReportFile(null);
    setCorporateDocs([]);
    setCorpDocCategory("");
    setCorpDocFile(null);
  }

  // --- Step 1: CAC number -------------------------------------------------
  function handleCacSubmit(e) {
    e.preventDefault();
    if (!cacNumber.trim()) return;

    withLoading("Looking up your company...", async () => {
      const { data, error: dbError } = await supabase
        .from(CAC_TABLE)
        .select(COMPANY_NAME_COLUMN)
        .eq(CAC_NUMBER_COLUMN, cacNumber.trim())
        .maybeSingle();

      if (dbError) {
        setError("Something went wrong looking up that CAC number. Please try again.");
        return;
      }
      if (!data) {
        setError("No company found for that CAC number. Please check and try again.");
        return;
      }
      setCompanyName(data[COMPANY_NAME_COLUMN]);
      setStep(STEP.CONFIRM_COMPANY);
    });
  }

  // --- Step 2: confirm company name ---------------------------------------
  function handleConfirmYes() {
    setStep(STEP.TIN);
  }

  function handleConfirmNo() {
    const nextCount = rejectionCount + 1;
    setRejectionCount(nextCount);
    if (nextCount > MAX_REJECTIONS) {
      setStep(STEP.BLOCKED);
      return;
    }
    setCompanyName("");
    setCacNumber("");
    setStep(STEP.CAC);
  }

  // --- Step 3: TIN ----------------------------------------------------------
  function handleTinSubmit(e) {
    e.preventDefault();
    if (!tin.trim()) return;

    withLoading("Verifying TIN...", async () => {
      const { data, error: dbError } = await supabase
        .from(CAC_TABLE)
        .select(COMPANY_NAME_COLUMN)
        .eq(TIN_COLUMN, tin.trim())
        .maybeSingle();

      if (dbError) {
        setError("Something went wrong verifying that TIN. Please try again.");
        return;
      }
      if (!data || !namesMatch(data[COMPANY_NAME_COLUMN], companyName)) {
        setError("CAC/TIN number mismatch.");
        return;
      }
      setStep(STEP.DIRECTORS);
    });
  }

  // --- Step 4: directors list ---------------------------------------------
  function handleAddDirector() {
    setNinInput("");
    setCurrentDirector(null);
    setError(null);
    setStep(STEP.DIRECTOR_NIN);
  }

  function handleDirectorsProceed() {
    if (directors.length < MIN_DIRECTORS) {
      setError(`Add at least ${MIN_DIRECTORS} directors before proceeding.`);
      return;
    }
    setError(null);
    setStep(STEP.COMPANY_ADDRESS);
  }

  // --- Step 5: director NIN -------------------------------------------------
  function handleNinSubmit(e) {
    e.preventDefault();
    if (!ninInput.trim()) return;

    withLoading("Fetching your details...", async () => {
      const { data, error: dbError } = await supabase
        .from(NIN_TABLE)
        .select(NIN_FIELDS)
        .eq(NIN_COLUMN, ninInput.trim())
        .maybeSingle();

      if (dbError) {
        setError("Something went wrong fetching NIN details. Please try again.");
        return;
      }
      if (!data) {
        setError("No record found for that NIN. Please check and try again.");
        return;
      }
      setCurrentDirector({ nin: ninInput.trim(), ...data });
      setStep(STEP.DIRECTOR_NIN_CONFIRM);
    });
  }

  // --- Step 6: confirm NIN-derived details ---------------------------------
  function handleNinLooksGood() {
    setBvnInput("");
    setStep(STEP.DIRECTOR_BVN);
  }

  // --- Step 7: director BVN -------------------------------------------------
  function handleBvnSubmit(e) {
    e.preventDefault();
    if (!bvnInput.trim()) return;

    withLoading("Verifying BVN...", async () => {
      const { data, error: dbError } = await supabase
        .from(BVN_TABLE)
        .select(BVN_FIELDS)
        .eq(BVN_COLUMN, bvnInput.trim())
        .maybeSingle();

      if (dbError) {
        setError("Something went wrong verifying that BVN. Please try again.");
        return;
      }
      if (
        !data ||
        !namesMatch(data.first_name, currentDirector?.first_name) ||
        !namesMatch(data.last_name, currentDirector?.last_name)
      ) {
        setError("BVN/NIN name mismatch.");
        return;
      }

      setCurrentDirector((prev) => ({ ...prev, bvn: bvnInput.trim() }));
      setPassportPhotoFile(null);
      setStep(STEP.DIRECTOR_PASSPORT_PHOTO);
    });
  }

  // --- Step 8: director passport photograph --------------------------------
  function handleDirectorPassportPhotoSubmit(e) {
    e.preventDefault();
    if (!passportPhotoFile) {
      setError("Please select a passport photograph to upload.");
      return;
    }

    withLoading("Uploading passport photograph...", async () => {
      try {
        const directorIndex = directors.length; // position this director will take
        const reference = await uploadDirectorPassportPhoto(passportPhotoFile, draftId, directorIndex);
        setCurrentDirector((prev) => ({ ...prev, passportPhoto: reference }));
        setPassportPhotoFile(null);
        setSignatureFile(null);
        setStep(STEP.DIRECTOR_SIGNATURE);
      } catch (err) {
        console.error("Passport photograph upload failed:", err);
        setError("Something went wrong uploading the passport photograph. Please try again.");
      }
    });
  }

  // --- Step 8b: director signature specimen ---------------------------------
  // Compared (by signature-verification/) against a signature found on this
  // director's OWN government-ID document, uploaded next - see that
  // service's README for how reliable this actually is.
  function handleDirectorSignatureSubmit(e) {
    e.preventDefault();
    if (!signatureFile) {
      setError("Please select a signature specimen to upload.");
      return;
    }

    withLoading("Uploading signature specimen...", async () => {
      try {
        const directorIndex = directors.length; // same position the passport photo was just uploaded under
        const reference = await uploadDirectorSignatureSpecimen(signatureFile, draftId, directorIndex);
        setCurrentDirector((prev) => ({ ...prev, signature: reference }));
        setSignatureFile(null);
        setGovernmentIdCategory("");
        setGovernmentIdFile(null);
        setStep(STEP.DIRECTOR_GOVERNMENT_ID);
      } catch (err) {
        console.error("Signature specimen upload failed:", err);
        setError("Something went wrong uploading the signature specimen. Please try again.");
      }
    });
  }

  // --- Step 8c: director's own government ID ---------------------------------
  // Compared against THIS director's own passport photo/signature (not a
  // shared, application-wide document) by face-verification/ and
  // signature-verification/ - see storage.py in each of those services for
  // how the directorIndex embedded in the filename is used to pair them up.
  function handleDirectorGovernmentIdSubmit(e) {
    e.preventDefault();
    if (!governmentIdCategory) {
      setError("Please select the type of government ID you're uploading.");
      return;
    }
    if (!governmentIdFile) {
      setError("Please select a government ID document to upload.");
      return;
    }

    withLoading("Uploading government ID...", async () => {
      try {
        const directorIndex = directors.length; // same position the photo/signature were just uploaded under
        const reference = await uploadDirectorGovernmentId(
          governmentIdFile,
          draftId,
          directorIndex,
          governmentIdCategory
        );
        setDirectors((prev) => [...prev, { ...currentDirector, governmentId: reference }]);
        setCurrentDirector(null);
        setGovernmentIdCategory("");
        setGovernmentIdFile(null);
        setStep(STEP.DIRECTORS);
      } catch (err) {
        console.error("Government ID upload failed:", err);
        setError("Something went wrong uploading the government ID. Please try again.");
      }
    });
  }

  // --- Step 9: company address (text, not a document) -----------------------
  function handleCompanyAddressSubmit(e) {
    e.preventDefault();
    if (!companyAddress.trim()) {
      setError("Please enter the company's address.");
      return;
    }
    setError(null);
    setStep(STEP.UTILITY_BILL);
  }

  // --- Step 10: utility bill (checked against pedco_electricity_registry) ---
  function handleUtilityBillSubmit(e) {
    e.preventDefault();
    if (!utilityBillFile) {
      setError("Please select the utility bill to upload.");
      return;
    }
    withLoading("Uploading utility bill...", async () => {
      try {
        await uploadCorporateDocument(utilityBillFile, "proof_of_address", draftId);
        setStep(STEP.CAC_CERTIFICATE_UPLOAD);
      } catch (err) {
        console.error("Utility bill upload failed:", err);
        setError("Something went wrong uploading the utility bill. Please try again.");
      }
    });
  }

  // --- Step 11: CAC certificate (checked against cac_tin_registry) ----------
  function handleCacCertificateSubmit(e) {
    e.preventDefault();
    if (!cacCertificateFile) {
      setError("Please select the CAC certificate to upload.");
      return;
    }
    withLoading("Uploading CAC certificate...", async () => {
      try {
        await uploadCorporateDocument(cacCertificateFile, "cac_certificate", draftId);
        setStep(STEP.BOARD_RESOLUTION);
      } catch (err) {
        console.error("CAC certificate upload failed:", err);
        setError("Something went wrong uploading the CAC certificate. Please try again.");
      }
    });
  }

  // --- Step 12: board resolution form (not AI-verified yet) -----------------
  function handleBoardResolutionSubmit(e) {
    e.preventDefault();
    if (!boardResolutionFile) {
      setError("Please select the board resolution form to upload.");
      return;
    }
    withLoading("Uploading board resolution form...", async () => {
      try {
        await uploadCorporateDocument(boardResolutionFile, "board_resolution_form", draftId);
        setStep(STEP.STATUS_REPORT);
      } catch (err) {
        console.error("Board resolution form upload failed:", err);
        setError("Something went wrong uploading the board resolution form. Please try again.");
      }
    });
  }

  // --- Step 13: CAC status report (checked against cac_tin_registry) --------
  function handleStatusReportSubmit(e) {
    e.preventDefault();
    if (!statusReportFile) {
      setError("Please select the status report to upload.");
      return;
    }
    withLoading("Uploading status report...", async () => {
      try {
        await uploadCorporateDocument(statusReportFile, "cac_status_report", draftId);
        setStep(STEP.CORPORATE_DOCUMENTS);
      } catch (err) {
        console.error("Status report upload failed:", err);
        setError("Something went wrong uploading the status report. Please try again.");
      }
    });
  }

  // --- Step 14: corporate documents ------------------------------------------
  function handleCorporateDocSubmit(e) {
    e.preventDefault();
    if (!corpDocCategory) {
      setError("Please select a document type.");
      return;
    }
    if (!corpDocFile) {
      setError("Please select a file to upload.");
      return;
    }

    withLoading("Uploading document...", async () => {
      try {
        const reference = await uploadCorporateDocument(corpDocFile, corpDocCategory, draftId);
        const label = CORPORATE_DOCUMENT_TYPES.find((d) => d.id === corpDocCategory)?.label ?? corpDocCategory;
        setCorporateDocs((prev) => [
          ...prev,
          { category: corpDocCategory, label, fileName: corpDocFile.name, reference },
        ]);
        setCorpDocCategory("");
        setCorpDocFile(null);
      } catch (err) {
        console.error("Corporate document upload failed:", err);
        setError("Something went wrong uploading that document. Please try again.");
      }
    });
  }

async function handleCorporateDocsFinish() {
  // A selected document type/file only gets uploaded when "Upload" is
  // clicked - without this check, clicking "Submit Application" instead
  // silently discards whatever was staged here, with no indication
  // anything was lost.
  if (corpDocCategory || corpDocFile) {
    setError(
      corpDocFile
        ? 'You have a file selected that hasn\'t been uploaded yet. Click "Upload" to add it, or clear the selection below before submitting.'
        : 'You have a document type selected but no file chosen. Pick a file and click "Upload", or clear the selection below before submitting.'
    );
    return;
  }

  if (directors.length < MIN_DIRECTORS) {
    setError(`Add at least ${MIN_DIRECTORS} directors before submitting.`);
    return;
  }

  const directorNins = directors
    .map((director) => director.nin)
    .filter(Boolean);

  if (directorNins.length === 0) {
    setError("No verified director NINs were found.");
    return;
  }

  await withLoading("Submitting your application...", async () => {
    try {
      const response = await submitCorporateWizardApplication({
        applicationId: draftId,
        companyName,
        cacNumber,
        tin,
        directorNins,
        companyAddress,
      });

      setSubmissionResult(response);
      setStep(STEP.COMING_SOON);
    } catch (err) {
      console.error("Application submission failed:", err);
      setError(
        err.message || "Something went wrong submitting the application."
      );
    }
  });
}

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  const showCompanyHeader = [
    STEP.DIRECTORS,
    STEP.DIRECTOR_NIN,
    STEP.DIRECTOR_NIN_CONFIRM,
    STEP.DIRECTOR_BVN,
    STEP.DIRECTOR_PASSPORT_PHOTO,
    STEP.DIRECTOR_SIGNATURE,
    STEP.DIRECTOR_GOVERNMENT_ID,
    STEP.COMPANY_ADDRESS,
    STEP.UTILITY_BILL,
    STEP.CAC_CERTIFICATE_UPLOAD,
    STEP.BOARD_RESOLUTION,
    STEP.STATUS_REPORT,
    STEP.CORPORATE_DOCUMENTS,
    STEP.COMING_SOON,
  ].includes(step);

  const isWideStep = step === STEP.DIRECTORS || step === STEP.CORPORATE_DOCUMENTS;

  return (
    <div className="ow-page">
      {showCompanyHeader && <CompanyHeader companyName={companyName} />}
      {loading && <MoneyLoader message={loadingMessage} />}

      <div className={`ow-card ${isWideStep ? "ow-card-wide" : ""}`}>
        {error && <p className="ow-error">{error}</p>}

        {step === STEP.CAC && (
          <form onSubmit={handleCacSubmit} className="ow-form">
            <h2>What's your company's CAC number?</h2>
            <input
              type="text"
              value={cacNumber}
              onChange={(e) => setCacNumber(e.target.value)}
              placeholder="RC1234567"
              autoFocus
            />
            <button type="submit" className="ow-btn-primary">Next</button>
          </form>
        )}

        {step === STEP.CONFIRM_COMPANY && (
          <div className="ow-form">
            <h2>Is this your company?</h2>
            <p className="ow-company-name">{companyName}</p>
            <div className="ow-btn-row">
              <button className="ow-btn-primary" onClick={handleConfirmYes}>
                Yes, proceed
              </button>
              <button className="ow-btn-ghost" onClick={handleConfirmNo}>
                No, take me back
              </button>
            </div>
          </div>
        )}

        {step === STEP.BLOCKED && (
          <div className="ow-form">
            <h2>You have been blocked.</h2>
            <p>Too many failed attempts. Please contact support to continue.</p>
          </div>
        )}

        {step === STEP.TIN && (
          <form onSubmit={handleTinSubmit} className="ow-form">
            <h2>What's your company's TIN?</h2>
            <input
              type="text"
              value={tin}
              onChange={(e) => setTin(e.target.value)}
              placeholder="TIN number"
              autoFocus
            />
            <button type="submit" className="ow-btn-primary">Next</button>
          </form>
        )}

        {step === STEP.DIRECTORS && (
          <div className="ow-form">
            <div className="ow-section-header">
              <div className="ow-section-icon">🏛️</div>
              <div>
                <h2>Add Directors</h2>
                <p className="ow-subtitle">
                  Add all directors of the corporate entity. Opening a corporate account requires at least{" "}
                  {MIN_DIRECTORS} directors.
                </p>
              </div>
            </div>

            <div className="ow-directors-list-section">
              <h3>Added Directors ({directors.length})</h3>
              <p className="ow-subtitle">List of directors already added.</p>

              {directors.length === 0 ? (
                <p>No directors added yet.</p>
              ) : (
                <table className="ow-table">
                  <thead>
                    <tr>
                      <th>First Name</th>
                      <th>Middle Name</th>
                      <th>Last Name</th>
                    </tr>
                  </thead>
                  <tbody>
                    {directors.map((d, i) => (
                      <tr key={i}>
                        <td>
                          <span className="ow-avatar-badge">{initials(d.first_name, d.last_name)}</span>
                          {d.first_name}
                        </td>
                        <td>{d.middle_name || "—"}</td>
                        <td>{d.last_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <button className="ow-btn-outline" onClick={handleAddDirector}>
              + Add Director
            </button>

            <div className="ow-btn-row ow-btn-row-end">
              <button className="ow-btn-ghost" onClick={handleWizardCancel}>Cancel</button>
              <button className="ow-btn-primary" onClick={handleDirectorsProceed}>Proceed →</button>
            </div>
          </div>
        )}

        {step === STEP.DIRECTOR_NIN && (
          <form onSubmit={handleNinSubmit} className="ow-form">
            <h2>Director's NIN</h2>
            <input
              type="text"
              value={ninInput}
              onChange={(e) => setNinInput(e.target.value)}
              placeholder="NIN"
              autoFocus
            />
            <button type="submit" className="ow-btn-primary">Next</button>
          </form>
        )}

        {step === STEP.DIRECTOR_NIN_CONFIRM && currentDirector && (
          <div className="ow-form">
            <h2>Confirm details</h2>
            <div className="ow-readonly-fields">
              <label>First name<input value={currentDirector.first_name ?? ""} readOnly /></label>
              <label>Middle name<input value={currentDirector.middle_name ?? ""} readOnly /></label>
              <label>Last name<input value={currentDirector.last_name ?? ""} readOnly /></label>
              <label>Email<input value={currentDirector.email ?? ""} readOnly /></label>
              <label>Phone number<input value={currentDirector.phone_number ?? ""} readOnly /></label>
              <label>Date of birth<input value={currentDirector.date_of_birth ?? ""} readOnly /></label>
            </div>
            <button className="ow-btn-primary" onClick={handleNinLooksGood}>
              Everything looks alright
            </button>
          </div>
        )}

        {step === STEP.DIRECTOR_BVN && (
          <form onSubmit={handleBvnSubmit} className="ow-form">
            <h2>Director's BVN</h2>
            <input
              type="text"
              value={bvnInput}
              onChange={(e) => setBvnInput(e.target.value)}
              placeholder="BVN"
              autoFocus
            />
            <button type="submit" className="ow-btn-primary">Next</button>
          </form>
        )}

        {step === STEP.DIRECTOR_PASSPORT_PHOTO && currentDirector && (
          <form onSubmit={handleDirectorPassportPhotoSubmit} className="ow-form">
            <h2>Upload passport photograph</h2>
            <p className="ow-subtitle">
              Upload a passport photograph for {currentDirector.first_name} {currentDirector.last_name}.
            </p>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp"
              onChange={(e) => setPassportPhotoFile(e.target.files?.[0] ?? null)}
            />
            {passportPhotoFile && <span className="ow-filename">{passportPhotoFile.name}</span>}
            <button type="submit" className="ow-btn-primary">Upload &amp; continue</button>
          </form>
        )}

        {step === STEP.DIRECTOR_SIGNATURE && currentDirector && (
          <form onSubmit={handleDirectorSignatureSubmit} className="ow-form">
            <h2>Upload signature specimen</h2>
            <p className="ow-subtitle">
              Upload a clear photo of {currentDirector.first_name} {currentDirector.last_name}'s signature. This is
              compared against the signature on their government ID.
            </p>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp"
              onChange={(e) => setSignatureFile(e.target.files?.[0] ?? null)}
            />
            {signatureFile && <span className="ow-filename">{signatureFile.name}</span>}
            <button type="submit" className="ow-btn-primary">Upload &amp; continue</button>
          </form>
        )}

        {step === STEP.DIRECTOR_GOVERNMENT_ID && currentDirector && (
          <form onSubmit={handleDirectorGovernmentIdSubmit} className="ow-form">
            <h2>Upload government ID</h2>
            <p className="ow-subtitle">
              Upload a valid government-issued ID for {currentDirector.first_name} {currentDirector.last_name} -
              International Passport, Driver's License, Voter's Card, or National ID Card. This is checked against
              their photo and signature.
            </p>
            <label>
              ID type
              <select value={governmentIdCategory} onChange={(e) => setGovernmentIdCategory(e.target.value)}>
                <option value="">Select ID type</option>
                {DIRECTOR_GOVERNMENT_ID_TYPES.map((type) => (
                  <option key={type.id} value={type.id}>{type.label}</option>
                ))}
              </select>
            </label>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              onChange={(e) => setGovernmentIdFile(e.target.files?.[0] ?? null)}
            />
            {governmentIdFile && <span className="ow-filename">{governmentIdFile.name}</span>}
            <button type="submit" className="ow-btn-primary">Upload &amp; continue</button>
          </form>
        )}

        {step === STEP.COMPANY_ADDRESS && (
          <form onSubmit={handleCompanyAddressSubmit} className="ow-form">
            <h2>What's the company's address?</h2>
            <p className="ow-subtitle">
              Enter the corporate entity's full registered address. This is checked against the address on file
              for your utility bill.
            </p>
            <input
              type="text"
              value={companyAddress}
              onChange={(e) => setCompanyAddress(e.target.value)}
              placeholder="e.g. 1621 Butler Dr, Lagos, Nigeria"
              autoFocus
            />
            <button type="submit" className="ow-btn-primary">Next</button>
          </form>
        )}

        {step === STEP.UTILITY_BILL && (
          <form onSubmit={handleUtilityBillSubmit} className="ow-form">
            <h2>Upload utility bill</h2>
            <p className="ow-subtitle">
              Upload a recent electricity bill for the company. The invoice number and address are checked
              against our records.
            </p>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              onChange={(e) => setUtilityBillFile(e.target.files?.[0] ?? null)}
            />
            {utilityBillFile && <span className="ow-filename">{utilityBillFile.name}</span>}
            <button type="submit" className="ow-btn-primary">Upload &amp; continue</button>
          </form>
        )}

        {step === STEP.CAC_CERTIFICATE_UPLOAD && (
          <form onSubmit={handleCacCertificateSubmit} className="ow-form">
            <h2>Upload CAC certificate</h2>
            <p className="ow-subtitle">
              Upload the company's CAC certificate. The RC number and company name are checked against our
              records.
            </p>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              onChange={(e) => setCacCertificateFile(e.target.files?.[0] ?? null)}
            />
            {cacCertificateFile && <span className="ow-filename">{cacCertificateFile.name}</span>}
            <button type="submit" className="ow-btn-primary">Upload &amp; continue</button>
          </form>
        )}

        {step === STEP.BOARD_RESOLUTION && (
          <form onSubmit={handleBoardResolutionSubmit} className="ow-form">
            <h2>Upload board resolution form</h2>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              onChange={(e) => setBoardResolutionFile(e.target.files?.[0] ?? null)}
            />
            {boardResolutionFile && <span className="ow-filename">{boardResolutionFile.name}</span>}
            <button type="submit" className="ow-btn-primary">Upload &amp; continue</button>
          </form>
        )}

        {step === STEP.STATUS_REPORT && (
          <form onSubmit={handleStatusReportSubmit} className="ow-form">
            <h2>Upload CAC status report</h2>
            <p className="ow-subtitle">
              Upload the Business Affairs Commission status form. The RC number, phone number, email, and
              registration date are checked against our records.
            </p>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              onChange={(e) => setStatusReportFile(e.target.files?.[0] ?? null)}
            />
            {statusReportFile && <span className="ow-filename">{statusReportFile.name}</span>}
            <button type="submit" className="ow-btn-primary">Upload &amp; continue</button>
          </form>
        )}

        {step === STEP.CORPORATE_DOCUMENTS && (
          <div className="ow-form">
            <h2>Upload Corporate Documents</h2>
            <p className="ow-subtitle">Upload each of the required documents for the corporate entity below.</p>

            {corporateDocs.length > 0 && (
              <div className="ow-directors-list-section">
                <h3>Uploaded Documents ({corporateDocs.length})</h3>
                <ul className="ow-doc-list">
                  {corporateDocs.map((doc, i) => (
                    <li key={i}>
                      <span>{doc.label}</span>
                      <span className="ow-doc-filename">{doc.fileName}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <form onSubmit={handleCorporateDocSubmit} className="ow-doc-upload-form">
              <label>
                Document type
                <select value={corpDocCategory} onChange={(e) => setCorpDocCategory(e.target.value)}>
                  <option value="">Select document type</option>
                  {CORPORATE_DOCUMENT_TYPES.map((doc) => (
                    <option key={doc.id} value={doc.id}>{doc.label}</option>
                  ))}
                </select>
              </label>
              <input
                key={corpDocFileInputKey}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.pdf"
                onChange={(e) => setCorpDocFile(e.target.files?.[0] ?? null)}
              />
              <button type="submit" className="ow-btn-primary">Upload</button>
              {(corpDocCategory || corpDocFile) && (
                <button type="button" className="ow-btn-ghost" onClick={handleClearCorpDocSelection}>
                  Clear selection
                </button>
              )}
            </form>

            <div className="ow-btn-row ow-btn-row-end">
              <button className="ow-btn-ghost" onClick={handleWizardCancel}>Cancel</button>
              <button className="ow-btn-primary" onClick={handleCorporateDocsFinish}disabled={loading}>{loading ? "Submitting..." : "Submit Application"}</button>            </div>
          </div>
        )}

       {step === STEP.COMING_SOON && (
  <div className="ow-form ow-success">
    <div className="ow-success-icon">✓</div>

    <h2>Application submitted</h2>

    <p>
      Your application for <strong>{companyName}</strong> has been
      successfully submitted and is now pending review.
    </p>

    {submissionResult?.application_reference && (
      <div className="ow-reference">
        <span>Application Reference</span>
        <strong>{submissionResult.application_reference}</strong>
      </div>
    )}

    <p className="ow-subtitle">
      We will review the submitted information and documents and update
      the application status when processing begins.
    </p>
  </div>
)}
      </div>
    </div>
  );
}