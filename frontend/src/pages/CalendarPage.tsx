import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function CalendarPage() {
  return (
    <ModuleScaffold
      moduleKey="calendar"
      requirements={[
        "Historical observations spanning multiple years, not only the last 30 days.",
        "FIRMS availability and missing-date records, so empty days are never read as zero activity.",
        "Calendar aggregates precomputed per region, sensor and metric.",
      ]}
    />
  );
}
