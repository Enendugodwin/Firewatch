import { create } from "zustand";
import { persist } from "zustand/middleware";

import { addDays, formatUtcDate } from "@/lib/time";

export type ThemeName = "dark" | "contrast";
export type RangePreset = "24h" | "7d" | "30d" | "90d" | "custom";

export const RANGE_PRESETS: { value: RangePreset; label: string; days: number | null }[] = [
  { value: "24h", label: "Last 24 hours", days: 1 },
  { value: "7d", label: "Last 7 days", days: 7 },
  { value: "30d", label: "Last 30 days", days: 30 },
  { value: "90d", label: "Last 90 days", days: 90 },
  { value: "custom", label: "Custom range", days: null },
];

export interface DateRange {
  preset: RangePreset;
  start: string;
  end: string;
}

export interface UiState {
  theme: ThemeName;
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  commandOpen: boolean;
  dateRange: DateRange;
  setTheme: (theme: ThemeName) => void;
  toggleTheme: () => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebarCollapsed: () => void;
  setCommandOpen: (open: boolean) => void;
  setPreset: (preset: RangePreset) => void;
  setCustomRange: (start: string, end: string) => void;
}

export function rangeForPreset(preset: RangePreset): Pick<DateRange, "start" | "end"> {
  const days = RANGE_PRESETS.find((item) => item.value === preset)?.days ?? 7;
  const today = new Date();
  return {
    start: formatUtcDate(addDays(today, -(days - 1))),
    end: formatUtcDate(today),
  };
}

function initialRange(): DateRange {
  return { preset: "7d", ...rangeForPreset("7d") };
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      theme: "dark",
      sidebarOpen: false,
      sidebarCollapsed: false,
      commandOpen: false,
      dateRange: initialRange(),

      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set({ theme: get().theme === "dark" ? "contrast" : "dark" }),
      toggleSidebar: () => set({ sidebarOpen: !get().sidebarOpen }),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      toggleSidebarCollapsed: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
      setCommandOpen: (commandOpen) => set({ commandOpen }),

      setPreset: (preset) => {
        if (preset === "custom") {
          set({ dateRange: { ...get().dateRange, preset } });
          return;
        }
        set({ dateRange: { preset, ...rangeForPreset(preset) } });
      },

      setCustomRange: (start, end) =>
        set({
          dateRange:
            start && end && start <= end
              ? { preset: "custom", start, end }
              : get().dateRange,
        }),
    }),
    {
      name: "firewatch.ui",
      partialize: (state) => ({
        theme: state.theme,
        sidebarCollapsed: state.sidebarCollapsed,
        dateRange: state.dateRange,
      }),
    },
  ),
);

export function useThemeSync() {
  const theme = useUiStore((state) => state.theme);
  return theme;
}
