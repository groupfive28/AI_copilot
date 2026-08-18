// Shared category ids MUST match the backend's DocumentCategory enum
// (backend/app/onboarding/schemas.py) - the two are not derived from a
// single source of truth, so keep them in sync by hand.
export const DOCUMENT_CATEGORIES = [
  { id: "cac_certificate", label: "CAC Certificate" },
  { id: "tin", label: "Tax Identification Number (TIN) Certificate" },
  { id: "nin", label: "National Identification Number (NIN)" },
  { id: "bvn", label: "Bank Verification Number (BVN)" },
  { id: "voters_card", label: "Voter's Card" },
  {
    id: "passport_or_drivers_license",
    label: "International Passport or Driver's License",
    hasSubtype: true,
    subtypeOptions: [
      { value: "passport", label: "International Passport" },
      { value: "drivers_license", label: "Driver's License" },
    ],
  },
  { id: "proof_of_address", label: "Proof of Address" },
];

// Standard CAC (Corporate Affairs Commission) registration categories.
// Proposed default - adjust freely, it's just this options list.
export const BUSINESS_TYPES = [
  { value: "business_name", label: "Business Name (BN)" },
  { value: "private_company_limited_by_shares", label: "Private Company Limited by Shares (LTD)" },
  { value: "public_limited_company", label: "Public Limited Company (PLC)" },
  { value: "company_limited_by_guarantee", label: "Company Limited by Guarantee (LTD/GTE)" },
  { value: "incorporated_trustees", label: "Incorporated Trustees (NGO)" },
];

// Used by the CAC/TIN/directors wizard's "Upload Corporate Documents" step.
// cac_certificate, proof_of_address, board_resolution_form, and
// cac_status_report are deliberately absent - each now has its own
// dedicated step earlier in the wizard (see OnboardingWizard.jsx's
// STEP.UTILITY_BILL/CAC_CERTIFICATE_UPLOAD/BOARD_RESOLUTION/STATUS_REPORT),
// so leaving them here too would let the same document be uploaded twice
// through two different paths. "address" is also removed - the company's
// address is now a real text field (STEP.COMPANY_ADDRESS), not a file
// upload. The govt_id_* options are also absent - a government ID is now
// collected per-director, alongside their NIN/BVN/photo/signature (see
// STEP.DIRECTOR_GOVERNMENT_ID), not once for the whole application - face
// verification and signature verification each compare a director against
// their own ID, not a shared one, so there's no longer a single
// application-wide "government ID" slot for this step to offer.
export const CORPORATE_DOCUMENT_TYPES = [
  { id: "certificate_of_incorporation", label: "Certificate of Incorporation (Contains CAC Number)" },
  { id: "account_name", label: "Account Name" },
  { id: "phone_number", label: "Phone Number" },
  { id: "email_address", label: "Email Address" },
  { id: "tin", label: "Tax Identification Number (TIN)" },
  { id: "nin", label: "National Identification Numbers (NIN)" },
  { id: "bvn", label: "Bank Verification Numbers (BVN)" },
  { id: "passport_photograph", label: "Passport Photograph" },
  { id: "signature_specimen", label: "Signature specimen for signatories" },
  { id: "memorandum_of_article", label: "Memorandum of Article" },
];

// Government ID categories a director can upload during their own block in
// the wizard (see OnboardingWizard.jsx's STEP.DIRECTOR_GOVERNMENT_ID) - the
// same 4 categories the non-wizard flow's DOCUMENT_CATEGORIES and the
// backend's PERSONAL_ID_REGISTRY_MAP already recognize.
export const DIRECTOR_GOVERNMENT_ID_TYPES = [
  { id: "govt_id_international_passport", label: "International Passport" },
  { id: "govt_id_drivers_license", label: "Driver's License" },
  { id: "govt_id_voters_card", label: "Voter's Card" },
  { id: "govt_id_national_id_card", label: "National ID Card" },
];