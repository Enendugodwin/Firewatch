import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { AnomaliesPage } from "@/pages/AnomaliesPage";
import { AssistantPage } from "@/pages/AssistantPage";
import { CalendarPage } from "@/pages/CalendarPage";
import { CloudReadinessPage } from "@/pages/CloudReadinessPage";
import { ExposurePage } from "@/pages/ExposurePage";
import { FireMapPage } from "@/pages/FireMapPage";
import { HarmonizationPage } from "@/pages/HarmonizationPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { QueryPage } from "@/pages/QueryPage";
import { RawArchivePage } from "@/pages/RawArchivePage";
import { RegionsPage } from "@/pages/RegionsPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { useAuthStatus } from "@/lib/authApi";

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useAuthStatus();
  if (isLoading) return null;
  if (data?.user?.role === "admin") return <>{children}</>;
  return <Navigate to="/login" replace />;
}

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="map" element={<FireMapPage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="query" element={<QueryPage />} />
        <Route path="harmonization" element={<HarmonizationPage />} />
        <Route path="anomalies" element={<AnomaliesPage />} />
        <Route path="regions" element={<RegionsPage />} />
        <Route path="exposure" element={<ExposurePage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="assistant" element={<AssistantPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route
          path="admin"
          element={
            <AdminRoute>
              <RawArchivePage />
            </AdminRoute>
          }
        />
        <Route path="login" element={<LoginPage />} />
        <Route path="infrastructure" element={<CloudReadinessPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
