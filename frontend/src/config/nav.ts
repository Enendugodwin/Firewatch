import type { LucideIcon } from "lucide-react";
import {
  CalendarDays,
  FileText,
  Globe2,
  LayoutDashboard,
  Layers,
  LineChart,
  Map as MapIcon,
  Radar,
  Search,
  Settings2,
  Cloud,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import type { ModuleStatus } from "@/types/api";

export interface NavItem {
  key: string;
  label: string;
  to: string;
  icon: LucideIcon;
  /** Delivery phase from the implementation plan. */
  phase: string;
  /** Short label used in the collapsed rail and command palette. */
  group: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    title: "Monitoring",
    items: [
      {
        key: "overview",
        label: "Overview",
        to: "/",
        icon: LayoutDashboard,
        phase: "Phase 4",
        group: "Global summary",
      },
      {
        key: "fire-map",
        label: "Global Fire Map",
        to: "/map",
        icon: MapIcon,
        phase: "Phase 4",
        group: "MapLibre hotspot map",
      },
    ],
  },
  {
    title: "History",
    items: [
      {
        key: "calendar",
        label: "Burning Calendar",
        to: "/calendar",
        icon: CalendarDays,
        phase: "Phase 5",
        group: "Historical activity",
      },
      {
        key: "analytics",
        label: "Analytics",
        to: "/analytics",
        icon: LineChart,
        phase: "Phase 6",
        group: "Trends and rankings",
      },
    ],
  },
  {
    title: "Science",
    items: [
      {
        key: "harmonization",
        label: "Sensor Intelligence",
        to: "/harmonization",
        icon: Layers,
        phase: "Phase 3",
        group: "MODIS / VIIRS harmonization",
      },
      {
        key: "anomalies",
        label: "Anomaly Detection",
        to: "/anomalies",
        icon: Radar,
        phase: "Phase 6",
        group: "Statistical baselines",
      },
    ],
  },
  {
    title: "Intelligence",
    items: [
      {
        key: "query",
        label: "Data Query",
        to: "/query",
        icon: Search,
        phase: "Phase 5",
        group: "Filter stored detections",
      },
      {
        key: "regions",
        label: "Regional Intelligence",
        to: "/regions",
        icon: Globe2,
        phase: "Phase 6",
        group: "Regional profiles",
      },
      {
        key: "exposure",
        label: "Exposure Analysis",
        to: "/exposure",
        icon: ShieldAlert,
        phase: "Phase 6",
        group: "Geographic screening",
      },
      {
        key: "reports",
        label: "Reports",
        to: "/reports",
        icon: FileText,
        phase: "Phase 7",
        group: "Exports and briefings",
      },
      {
        key: "assistant",
        label: "AI Assistant",
        to: "/assistant",
        icon: Sparkles,
        phase: "Phase 7",
        group: "Investigate with tools",
      },
    ],
  },
  {
    title: "Infrastructure",
    items: [
      {
        key: "cloud-readiness",
        label: "Cloud Readiness",
        to: "/infrastructure",
        icon: Cloud,
        phase: "Phase 9",
        group: "Storage, datasets and sync",
      },
    ],
  },
  {
    title: "System",
    items: [
      {
        key: "settings",
        label: "Settings",
        to: "/settings",
        icon: Settings2,
        phase: "Phase 1",
        group: "Status and administration",
      },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((section) => section.items);

export function findNavItemByKey(key: string): NavItem | undefined {
  return NAV_ITEMS.find((item) => item.key === key);
}

/** Static fallback status used before the API responds. */
export const DEFAULT_STATUS: Record<string, ModuleStatus> = Object.fromEntries(
  NAV_ITEMS.map((item) => [item.key, item.key === "settings" ? "in_progress" : "scaffolded"]),
);
