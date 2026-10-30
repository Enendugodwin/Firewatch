import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function ReportsPage() {
  return (
    <ModuleScaffold
      moduleKey="reports"
      requirements={[
        "Analytical queries stable enough to be cited in a document.",
        "Background workers for large exports, outside request handlers.",
        "Provenance: processing versions, observation identifiers and limitations per report.",
      ]}
    />
  );
}
