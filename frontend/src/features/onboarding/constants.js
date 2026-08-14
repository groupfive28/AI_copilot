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
