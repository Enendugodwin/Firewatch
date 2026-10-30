/** API contracts per module, mirroring the specification (§7). */

export interface EndpointContract {
  method: "GET" | "POST";
  path: string;
  purpose: string;
}

export const MODULE_ENDPOINTS: Record<string, EndpointContract[]> = {
  overview: [
    { method: "GET", path: "/api/v1/dashboard", purpose: "Global overview aggregates" },
    { method: "GET", path: "/api/v1/system/status", purpose: "Data freshness" },
  ],
  "fire-map": [
    { method: "GET", path: "/api/v1/fires", purpose: "Filtered observation search" },
    { method: "GET", path: "/api/v1/fires/geojson", purpose: "Map-ready features" },
  ],
  calendar: [
    { method: "GET", path: "/api/v1/calendar", purpose: "Daily activity for a region" },
    { method: "GET", path: "/api/v1/fires", purpose: "Cell drill-down observations" },
  ],
  analytics: [
    { method: "GET", path: "/api/v1/dashboard", purpose: "Trends and rankings" },
  ],
  harmonization: [
    { method: "GET", path: "/api/v1/harmonization/summary", purpose: "Match statistics" },
    { method: "GET", path: "/api/v1/harmonization/matches", purpose: "Inspected associations" },
  ],
  anomalies: [
    { method: "GET", path: "/api/v1/anomalies", purpose: "Anomaly evidence and baselines" },
  ],
  regions: [
    { method: "GET", path: "/api/v1/regions", purpose: "Region catalogue and profiles" },
  ],
  exposure: [
    { method: "GET", path: "/api/v1/exposure", purpose: "Distance bands and assets" },
  ],
  reports: [
    { method: "GET", path: "/api/v1/reports", purpose: "Generated reports" },
  ],
  assistant: [
    { method: "POST", path: "/api/v1/assistant/chat", purpose: "Tool-calling investigation" },
  ],
  settings: [
    { method: "GET", path: "/api/v1/system/sources", purpose: "Source registry" },
    { method: "GET", path: "/api/v1/admin/ingestion/jobs", purpose: "Ingestion history" },
  ],
};
