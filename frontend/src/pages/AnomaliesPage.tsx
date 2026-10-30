import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function AnomaliesPage() {
  return (
    <ModuleScaffold
      moduleKey="anomalies"
      requirements={[
        "Multi-year history per region, so seasonal baselines have enough samples.",
        "Stored baseline statistics (median, MAD, quantiles) with model versions.",
        "Data-completeness metadata, so gaps suppress alerts instead of inflating them.",
      ]}
    />
  );
}
