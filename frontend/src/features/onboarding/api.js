import { apiRequest } from "../../shared/api/client.js";
import { DOCUMENT_CATEGORIES } from "./constants.js";

/** Notifies the backend that a new application (with its uploaded documents) has arrived. */
export async function submitApplication(applicationId, fields, uploads) {
  const documents = DOCUMENT_CATEGORIES.filter((category) => uploads[category.id]?.reference).map((category) => {
    const entry = uploads[category.id];
    return {
      category: category.id,
      document_subtype: entry.subtype || null,
      file_name: entry.file.name,
      content_type: entry.file.type || null,
      storage_path: entry.reference.storagePath,
      download_url: entry.reference.downloadUrl,
    };
  });

  return apiRequest("/api/v1/onboarding/applications", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      application_id: applicationId,
      corporate_details: {
        cac_registration_number: fields.cacRegistrationNumber,
        company_name: fields.companyName,
        date_of_registration: fields.dateOfRegistration || null,
        business_type: fields.businessType,
        tin: fields.tin,
      },
      signatory: {
        full_name: fields.signatoryFullName,
        email: fields.signatoryEmail,
        phone_number: fields.signatoryPhoneNumber,
        designation: fields.signatoryDesignation,
      },
      documents,
    }),
  });
}

/**
 * Final submission for the new corporate onboarding wizard.
 */
export async function submitCorporateWizardApplication({
  applicationId,
  companyName,
  cacNumber,
  tin,
  directorNins,
  companyAddress,
}) {
  return apiRequest("/api/v1/onboarding/wizard-submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      application_id: applicationId,
      company_name: companyName,
      cac_number: cacNumber,
      tin,
      director_nins: directorNins,
      company_address: companyAddress || null,
    }),
  });
}
