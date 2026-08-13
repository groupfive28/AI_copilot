import UploadPage from "./features/upload/UploadPage.jsx";
import HealthStatus from "./shared/components/HealthStatus.jsx";

export default function App() {
  return (
    <div className="app">
      <HealthStatus />
      <UploadPage />
    </div>
  );
}
