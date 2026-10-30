import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function AnalyticsPage() {
  return (
    <ModuleScaffold
      moduleKey="analytics"
      requirements={[
        "Ingested observations, so trends and rankings are computed rather than mocked.",
        "Region boundaries loaded for country and admin-area comparisons.",
        "Pre-aggregated daily statistics to keep interactive queries fast.",
      ]}
    />
  );
}
