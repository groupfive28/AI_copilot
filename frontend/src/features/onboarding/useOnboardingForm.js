import { useState } from "react";

const INITIAL_FIELDS = {
  // CAC certificate details
  cacRegistrationNumber: "",
  companyName: "",
  dateOfRegistration: "",
  businessType: "",
  // TIN
  tin: "",
  // Signatory information
  signatoryFullName: "",
  signatoryEmail: "",
  signatoryPhoneNumber: "",
  signatoryDesignation: "",
};

const REQUIRED_FIELDS = [
  "cacRegistrationNumber",
  "companyName",
  "businessType",
  "tin",
  "signatoryFullName",
  "signatoryEmail",
  "signatoryPhoneNumber",
  "signatoryDesignation",
];

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function useOnboardingForm() {
  const [fields, setFields] = useState(INITIAL_FIELDS);
  const [errors, setErrors] = useState({});

  function setField(name, value) {
    setFields((prev) => ({ ...prev, [name]: value }));
  }

  function validate() {
    const nextErrors = {};

    for (const name of REQUIRED_FIELDS) {
      if (!String(fields[name] ?? "").trim()) {
        nextErrors[name] = "Required";
      }
    }

    if (fields.signatoryEmail && !EMAIL_PATTERN.test(fields.signatoryEmail)) {
      nextErrors.signatoryEmail = "Enter a valid email address";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  return { fields, errors, setField, validate };
}
