import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function FireMapPage() {
  return (
    <ModuleScaffold
      moduleKey="fire-map"
      requirements={[
        "Stored observations with coordinates, so the viewport query has something to return.",
        "A vector-tile or server-side aggregation layer for global zoom levels.",
        "A tile/dimension baseline per sensor so clusters are never presented as fire counts.",
      ]}
    />
  );
}
