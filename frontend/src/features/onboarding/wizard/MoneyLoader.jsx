import "./onboardingWizard.css";

export default function MoneyLoader({ message = "Just a moment..." }) {
  return (
    <div className="ow-loader-overlay">
      <div className="ow-loader-coin">₦</div>
      <p className="ow-loader-text">{message}</p>
    </div>
  );
}