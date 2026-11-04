import { SlidersHorizontal } from "lucide-react";

import type { MapThemeId } from "./mapStyle";
import { DEFAULT_THEME, MAP_THEMES, THEME_ORDER } from "./mapStyle";

export interface MapFiltersState {
  theme: MapThemeId;
  modis: boolean;
  viirs: boolean;
  minFrp: number;
  minConfidence: "low" | "nominal" | "high";
  daynight: "all" | "D" | "N";
  heat: boolean;
  basemap: boolean;
  includeSynthetic: boolean;
  harmonized: boolean;
}

export const DEFAULT_FILTERS: MapFiltersState = {
  theme: DEFAULT_THEME,
  modis: true,
  viirs: true,
  minFrp: 0,
  minConfidence: "low",
  daynight: "all",
  heat: false,
  basemap: true,
  includeSynthetic: false,
  harmonized: false,
};

const label = "text-2xs font-light text-faint";
const control =
  "mt-[5px] w-full rounded-control border border-line/10 bg-canvas/70 px-2 py-[6px] font-mono text-2xs text-ink";

function Checkbox({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 py-[3px] text-xs font-light text-muted">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-3.5 rounded border-line/40 bg-transparent accent-[#60D58B]"
      />
      {children}
    </label>
  );
}

export function MapFilters({
  filters,
  onChange,
  hasSynthetic,
  onReset,
}: {
  filters: MapFiltersState;
  onChange: (next: MapFiltersState) => void;
  hasSynthetic: boolean;
  onReset: () => void;
}) {
  function patch(next: Partial<MapFiltersState>) {
    onChange({ ...filters, ...next });
  }

  return (
    <div className="w-[15.5rem] rounded-card border border-line/[0.1] bg-panel/95 px-[14px] py-[12px] shadow-lift backdrop-blur-glass">
      <div className="mb-[10px] flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-2xs font-medium uppercase tracking-[0.14em] text-muted">
          <SlidersHorizontal className="size-3" aria-hidden />
          Layers &amp; filters
        </span>
        <button
          type="button"
          onClick={onReset}
          className="text-3xs uppercase tracking-[0.1em] text-faint transition-colors duration-150 hover:text-muted"
        >
          Reset
        </button>
      </div>

      <div className="border-b border-line/[0.07] pb-[10px]">
        <span className={label}>Map theme</span>
        <div className="mt-[6px] grid grid-cols-2 gap-[5px]">
          {THEME_ORDER.map((id) => {
            const theme = MAP_THEMES[id];
            const active = filters.theme === id;
            return (
              <button
                key={id}
                type="button"
                aria-pressed={active}
                title={theme.hint}
                onClick={() => patch({ theme: id })}
                className={`flex items-center gap-[6px] rounded-control border px-[6px] py-[5px] text-3xs transition-colors duration-150 ${
                  active
                    ? "border-line/25 bg-line/[0.07] text-ink"
                    : "border-line/10 text-muted hover:border-line/20 hover:text-ink"
                }`}
              >
                <span
                  className="size-3 shrink-0 rounded-[3px] border border-line/20"
                  style={{
                    background: `linear-gradient(135deg, ${theme.swatch[0]} 0%, ${theme.swatch[1]} 100%)`,
                  }}
                  aria-hidden
                />
                {theme.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="space-y-[2px] border-b border-line/[0.07] pb-[10px] pt-[10px]">
        <Checkbox checked={filters.modis} onChange={(modis) => patch({ modis })}>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="size-1.5 rounded-full"
              style={{ backgroundColor: MAP_THEMES[filters.theme].sensor.MODIS }}
            />
            MODIS
          </span>
        </Checkbox>
        <Checkbox checked={filters.viirs} onChange={(viirs) => patch({ viirs })}>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="size-1.5 rounded-full"
              style={{ backgroundColor: MAP_THEMES[filters.theme].sensor.VIIRS }}
            />
            VIIRS
          </span>
        </Checkbox>
      </div>

      <div className="space-y-[9px] border-b border-line/[0.07] py-[10px]">
        <label className="block">
          <span className={label}>Minimum FRP · {filters.minFrp} MW</span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={filters.minFrp}
            onChange={(event) => patch({ minFrp: Number(event.target.value) })}
            className="mt-[6px] w-full accent-[#FB923C]"
          />
        </label>

        <label className="block">
          <span className={label}>Confidence</span>
          <select
            value={filters.minConfidence}
            onChange={(event) =>
              patch({ minConfidence: event.target.value as MapFiltersState["minConfidence"] })
            }
            className={control}
          >
            <option value="low">Any confidence</option>
            <option value="nominal">Nominal or higher</option>
            <option value="high">High only</option>
          </select>
        </label>

        <label className="block">
          <span className={label}>Day / night</span>
          <select
            value={filters.daynight}
            onChange={(event) =>
              patch({ daynight: event.target.value as MapFiltersState["daynight"] })
            }
            className={control}
          >
            <option value="all">Day and night</option>
            <option value="D">Daytime detections</option>
            <option value="N">Night-time detections</option>
          </select>
        </label>
      </div>

      <div className="space-y-[2px] pt-[9px]">
        <Checkbox checked={filters.heat} onChange={(heat) => patch({ heat })}>
          Density heatmap
        </Checkbox>
        <Checkbox checked={filters.basemap} onChange={(basemap) => patch({ basemap })}>
          Basemap (© OpenStreetMap)
        </Checkbox>
        <Checkbox
          checked={filters.harmonized}
          onChange={(harmonized) => patch({ harmonized })}
        >
          Harmonized view (dedupe MODIS-associated VIIRS)
        </Checkbox>
        {hasSynthetic ? (
          <Checkbox
            checked={filters.includeSynthetic}
            onChange={(includeSynthetic) => patch({ includeSynthetic })}
          >
            Include synthetic fixture
          </Checkbox>
        ) : null}
      </div>

      <div className="mt-[10px] flex items-center gap-2 border-t border-line/[0.07] pt-[9px]">
        <span className="text-3xs uppercase tracking-[0.1em] text-faint">FRP</span>
        <span className="flex-1" />
        {(["low", "medium", "high"] as const).map((tone) => (
          <span key={tone} className="inline-flex items-center gap-1 text-3xs text-faint">
            <span
              className="size-1.5 rounded-full"
              style={{ backgroundColor: MAP_THEMES[filters.theme].fire[tone] }}
            />
            {tone}
          </span>
        ))}
      </div>
    </div>
  );
}
