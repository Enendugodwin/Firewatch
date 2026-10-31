import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { AnomaliesPage } from "@/pages/AnomaliesPage";
import { AssistantPage } from "@/pages/AssistantPage";
import { CalendarPage } from "@/pages/CalendarPage";
import { ExposurePage } from "@/pages/ExposurePage";
import { FireMapPage } from "@/pages/FireMapPage";
import { HarmonizationPage } from "@/pages/HarmonizationPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { QueryPage } from "@/pages/QueryPage";
import { RegionsPage } from "@/pages/RegionsPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";

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
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
