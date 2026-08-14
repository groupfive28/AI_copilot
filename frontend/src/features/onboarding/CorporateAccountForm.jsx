import { BUSINESS_TYPES } from "./constants.js";

function Field({ label, name, fields, errors, setField, type = "text" }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={fields[name]}
        onChange={(e) => setField(name, e.target.value)}
        aria-invalid={Boolean(errors[name])}
      />
      {errors[name] && <span className="field-error">{errors[name]}</span>}
    </label>
  );
}

export default function CorporateAccountForm({ fields, errors, setField }) {
  return (
    <div className="form-card">
      <h2>Corporate account details</h2>

      <fieldset>
        <legend>CAC certificate details</legend>
        <Field label="RC / Registration number" name="cacRegistrationNumber" {...{ fields, errors, setField }} />
        <Field label="Registered company name" name="companyName" {...{ fields, errors, setField }} />
        <Field
          label="Date of registration"
          name="dateOfRegistration"
          type="date"
          {...{ fields, errors, setField }}
        />
        <label className="field">
          <span>Business type</span>
          <select
            value={fields.businessType}
            onChange={(e) => setField("businessType", e.target.value)}
            aria-invalid={Boolean(errors.businessType)}
          >
            <option value="">Select business type</option>
            {BUSINESS_TYPES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {errors.businessType && <span className="field-error">{errors.businessType}</span>}
        </label>
      </fieldset>

      <fieldset>
        <legend>Tax Identification Number</legend>
        <Field label="TIN" name="tin" {...{ fields, errors, setField }} />
      </fieldset>

      <fieldset>
        <legend>Signatory information</legend>
        <Field label="Full name" name="signatoryFullName" {...{ fields, errors, setField }} />
        <Field label="Email" name="signatoryEmail" type="email" {...{ fields, errors, setField }} />
        <Field label="Phone number" name="signatoryPhoneNumber" {...{ fields, errors, setField }} />
        <Field label="Designation" name="signatoryDesignation" {...{ fields, errors, setField }} />
      </fieldset>
    </div>
  );
}
