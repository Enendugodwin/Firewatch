import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function HarmonizationPage() {
  return (
    <ModuleScaffold
      moduleKey="harmonization"
      requirements={[
        "Canonical normalized records for MODIS and each VIIRS satellite, retaining raw values.",
        "An association pass with temporal, spatial and footprint components stored per pair.",
        "Explicit separation of raw observations, probable matches and estimated events.",
      ]}
    />
  );
}
