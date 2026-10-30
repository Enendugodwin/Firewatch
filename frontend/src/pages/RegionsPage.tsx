import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function RegionsPage() {
  return (
    <ModuleScaffold
      moduleKey="regions"
      requirements={[
        "Global administrative boundaries loaded as PostGIS geometry.",
        "Regional daily statistics, so a profile is a query result not a template.",
        "Support for custom polygons, circles and bounding boxes, all scope-checked.",
      ]}
    />
  );
}
