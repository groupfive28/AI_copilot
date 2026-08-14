import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";

import LandingPage from "./features/marketing/LandingPage.jsx";
import ApplicationDetailView from "./features/operations/ApplicationDetailView.jsx";
import ApplicationsListView from "./features/operations/ApplicationsListView.jsx";
import OperationsLayout from "./features/operations/OperationsLayout.jsx";
import VerificationResultsView from "./features/operations/VerificationResultsView.jsx";
import OnboardingPage from "./features/onboarding/OnboardingPage.jsx";
import HealthStatus from "./shared/components/HealthStatus.jsx";

function OnboardingShell() {
  return (
    <div className="app">
      <div className="app-top-bar">
        <HealthStatus />
        <Link to="/operations" className="app-cross-link">
          Operations dashboard →
        </Link>
      </div>
      <OnboardingPage />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes> 
        <Route path="/" element={<LandingPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/operations" element={<OperationsLayout />}>
          <Route index element={<ApplicationsListView />} />
          <Route path="applications/:applicationId" element={<ApplicationDetailView />} />
          <Route path="verification-results" element={<VerificationResultsView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
