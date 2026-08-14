import { useState } from "react";
import { supabase } from "../../../shared/supabase/client.js";
import { CORPORATE_DOCUMENT_TYPES } from "../constants.js";
import { uploadCorporateDocument, uploadDirectorPassportPhoto } from "./wizardStorage.js";
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
const NIN_COLUMN = "nin";
const NIN_FIELDS = "first_name,middle_name,last_name,email,phone_number,date_of_birth";

const BVN_TABLE = "bvn_registry";
const BVN_COLUMN = "bvn";
const BVN_FIELDS = "first_name,last_name,middle_name";

const MAX_REJECTIONS = 3; // "take me back" clicks allowed before block

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

  const [corporateDocs, setCorporateDocs] = useState([]);
  const [corpDocCategory, setCorpDocCategory] = useState("");
  const [corpDocFile, setCorpDocFile] = useState(null);

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
    if (directors.length === 0) {
      setError("Add at least one director before proceeding.");
      return;
    }
    setError(null);
    setStep(STEP.CORPORATE_DOCUMENTS);
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
        setDirectors((prev) => [...prev, { ...currentDirector, passportPhoto: reference }]);
        setCurrentDirector(null);
        setPassportPhotoFile(null);
        setStep(STEP.DIRECTORS);
      } catch (err) {
        setError("Something went wrong uploading the passport photograph. Please try again.");
      }
    });
  }

  // --- Step 9: corporate documents ------------------------------------------
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
        setError("Something went wrong uploading that document. Please try again.");
      }
    });
  }

  function handleCorporateDocsFinish() {
    setStep(STEP.COMING_SOON);
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
                <p className="ow-subtitle">Add all directors of the corporate entity. You can add multiple directors.</p>
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

        {step === STEP.CORPORATE_DOCUMENTS && (
          <div className="ow-form">
            <h2>Upload Corporate Documents</h2>
            <p className="ow-subtitle">Upload each of the required documents for the corporate entity below.</p>
            <p className="ow-note">
              Only upload <strong>one</strong> valid government-issued ID — International Passport, Driver's License,
              Voter's Card, or National ID Card. You don't need to provide more than one.
            </p>

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
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.pdf"
                onChange={(e) => setCorpDocFile(e.target.files?.[0] ?? null)}
              />
              <button type="submit" className="ow-btn-primary">Upload</button>
            </form>

            <div className="ow-btn-row ow-btn-row-end">
              <button className="ow-btn-ghost" onClick={handleWizardCancel}>Cancel</button>
              <button className="ow-btn-primary" onClick={handleCorporateDocsFinish}>Finish</button>
            </div>
          </div>
        )}

        {step === STEP.COMING_SOON && (
          <div className="ow-form">
            <h2>Coming soon</h2>
            <p>We'll build the rest of this flow later.</p>
          </div>
        )}
      </div>
    </div>
  );
}