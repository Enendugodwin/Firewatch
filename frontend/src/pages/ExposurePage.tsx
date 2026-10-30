import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function ExposurePage() {
  return (
    <ModuleScaffold
      moduleKey="exposure"
      requirements={[
        "Infrastructure datasets (OSM, WorldPop and similar) with licence attribution.",
        "PostGIS geodesic distance queries against detection points.",
        "Distance bands framed as geographic screening, never as fire threat.",
      ]}
    />
  );
}
