import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel } from "@/components/ui/Panel";
import { formatCount, formatFrp } from "@/lib/format";
import {
  addAsset,
  fetchAssets,
  fetchScreen,
  removeAsset,
} from "@/lib/intelligenceApi";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

export function ExposurePage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "exposure");
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [latitude, setLatitude] = useState("9.06");
  const [longitude, setLongitude] = useState("7.49");
  const [category, setCategory] = useState("facility");

  const assets = useQuery({
    queryKey: ["exposure", "assets"],
    queryFn: ({ signal }) => fetchAssets(signal),
    staleTime: 30_000,
  });

  const screen = useQuery({
    queryKey: ["exposure", "screen", dateRange.start, dateRange.end],
    queryFn: ({ signal }) => fetchScreen(dateRange.start, dateRange.end, signal),
    staleTime: 30_000,
    retry: 1,
  });

  const create = useMutation({
    mutationFn: () =>
      addAsset({
        name,
        latitude: Number(latitude),
        longitude: Number(longitude),
        category,
      }),
    onSuccess: () => {
      setName("");
      void queryClient.invalidateQueries({ queryKey: ["exposure"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => removeAsset(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["exposure"] });
    },
  });

  const rows = screen.data?.assets ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Intelligence"
        title="Exposure Analysis"
        status={module?.status}
        phase={module?.phase}
        description="Register the places you care about, then measure which detections fell within 50 km of them. No population or infrastructure dataset is bundled, so this is proximity — not a damage or risk score."
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        <Panel title="Watched assets" subtitle={`${assets.data?.length ?? 0} registered`}>
          <form
            className="grid gap-2 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (!name.trim()) return;
              create.mutate();
            }}
          >
            <label className="sm:col-span-2 text-2xs font-light text-faint">
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                aria-label="Asset name"
                placeholder="Depot, school, substation…"
                className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-[6px] text-2xs text-ink"
              />
            </label>
            <label className="text-2xs font-light text-faint">
              Latitude
              <input
                value={latitude}
                onChange={(event) => setLatitude(event.target.value)}
                aria-label="Asset latitude"
                className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-[6px] font-mono text-2xs text-ink"
              />
            </label>
            <label className="text-2xs font-light text-faint">
              Longitude
              <input
                value={longitude}
                onChange={(event) => setLongitude(event.target.value)}
                aria-label="Asset longitude"
                className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-[6px] font-mono text-2xs text-ink"
              />
            </label>
            <label className="sm:col-span-2 text-2xs font-light text-faint">
              Category
              <input
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                aria-label="Asset category"
                className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-[6px] text-2xs text-ink"
              />
            </label>
            <div className="sm:col-span-2">
              <button
                type="submit"
                disabled={create.isPending || !name.trim()}
                className="btn-primary inline-flex items-center gap-1.5 px-3 py-[6px] text-2xs disabled:opacity-40"
              >
                <Plus className="size-3" aria-hidden />
                Add asset
              </button>
            </div>
          </form>

          {assets.data && assets.data.length > 0 ? (
            <ul className="mt-4 space-y-[4px]">
              {assets.data.map((asset) => (
                <li
                  key={asset.id}
                  className="flex items-center justify-between gap-2 border-b border-line/[0.05] py-[5px] text-2xs last:border-0"
                >
                  <span className="min-w-0">
                    <span className="text-ink">{asset.name}</span>
                    <span className="ml-2 font-mono text-3xs text-faint">
                      {asset.latitude.toFixed(3)}, {asset.longitude.toFixed(3)}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => remove.mutate(asset.id)}
                    aria-label={`Remove ${asset.name}`}
                    className="rounded-full p-1 text-faint hover:text-danger"
                  >
                    <Trash2 className="size-3" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-2xs text-muted">
              No assets yet. Add one to screen detections nearby.
            </p>
          )}
        </Panel>

        <Panel
          title="Screening"
          subtitle={screen.data ? `Within ${screen.data.radius_km} km · ${dateRange.start} → ${dateRange.end}` : undefined}
        >
          {rows.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[32rem] border-collapse text-3xs">
                <thead>
                  <tr className="border-b border-line/[0.08] text-left uppercase tracking-[0.1em] text-faint">
                    <th className="py-[6px] pr-3 font-medium">Asset</th>
                    <th className="py-[6px] pr-3 text-right font-medium">Nearby detections</th>
                    <th className="py-[6px] pr-3 text-right font-medium">FRP max</th>
                    <th className="py-[6px] text-right font-medium">Nearest</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.asset_id} className="border-b border-line/[0.05] text-muted">
                      <td className="py-[6px] pr-3 text-ink">
                        {row.name}
                        <span className="ml-2 text-3xs text-faint">{row.category}</span>
                      </td>
                      <td className="py-[6px] pr-3 text-right font-mono">
                        {formatCount(row.detections_within_radius)}
                      </td>
                      <td className="py-[6px] pr-3 text-right font-mono">
                        {formatFrp(row.frp_max_mw)}
                      </td>
                      <td className="py-[6px] text-right font-mono">
                        {row.nearest ? `${row.nearest.distance_km.toFixed(1)} km` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={<MapPin className="size-4" aria-hidden />}
              title="Nothing to screen"
              description="Add an asset, or widen the period in the header."
            />
          )}
          {screen.data ? (
            <p className="mt-3 text-3xs font-light leading-relaxed text-faint">
              {screen.data.note} Scanned {formatCount(screen.data.observations_scanned)} detections
              {screen.data.truncated ? " (scan capped)" : ""}.
            </p>
          ) : null}
        </Panel>
      </div>
    </>
  );
}
