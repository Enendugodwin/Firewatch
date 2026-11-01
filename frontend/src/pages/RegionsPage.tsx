import { useQuery } from "@tanstack/react-query";
import { Globe2 } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel } from "@/components/ui/Panel";
import { formatCount, formatFrp } from "@/lib/format";
import { fetchRegions } from "@/lib/intelligenceApi";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

export function RegionsPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "regions");

  const regions = useQuery({
    queryKey: ["regions", dateRange.start, dateRange.end],
    queryFn: ({ signal }) => fetchRegions(dateRange.start, dateRange.end, signal),
    staleTime: 60_000,
    retry: 1,
  });

  const data = regions.data;

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Intelligence"
        title="Regional Intelligence"
        status={module?.status}
        phase={module?.phase}
        description="Activity ranked by region for the selected period. Regions are approximate centroid boxes from the offline gazetteer — deliberately not administrative boundaries."
      />

      <Panel
        title="Regional profiles"
        subtitle={data ? `${data.half_degrees}° half-box · sorted by detections` : undefined}
      >
        {regions.isLoading ? <p className="text-2xs text-muted">Ranking regions…</p> : null}
        {data && data.regions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] border-collapse text-3xs">
              <thead>
                <tr className="border-b border-line/[0.08] text-left uppercase tracking-[0.1em] text-faint">
                  <th className="py-[6px] pr-3 font-medium">Region</th>
                  <th className="py-[6px] pr-3 font-medium">ISO</th>
                  <th className="py-[6px] pr-3 text-right font-medium">Detections</th>
                  <th className="py-[6px] pr-3 text-right font-medium">Active days</th>
                  <th className="py-[6px] text-right font-medium">FRP sum</th>
                </tr>
              </thead>
              <tbody>
                {data.regions.map((region) => (
                  <tr key={region.name} className="border-b border-line/[0.05] text-muted">
                    <td className="py-[6px] pr-3 text-ink">{region.name}</td>
                    <td className="py-[6px] pr-3 font-mono text-faint">{region.iso ?? "—"}</td>
                    <td className="py-[6px] pr-3 text-right font-mono">
                      {formatCount(region.detections)}
                    </td>
                    <td className="py-[6px] pr-3 text-right font-mono">
                      {formatCount(region.active_days)}
                    </td>
                    <td className="py-[6px] text-right font-mono">{formatFrp(region.frp_sum_mw)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {data && data.regions.every((region) => region.detections === 0) ? (
          <EmptyState
            icon={<Globe2 className="size-4" aria-hidden />}
            title="No detections in this period"
            description="Nothing was stored for the selected range, so no region ranks."
          />
        ) : null}
        {data ? (
          <p className="mt-3 text-3xs font-light leading-relaxed text-faint">{data.note}</p>
        ) : null}
      </Panel>
    </>
  );
}
