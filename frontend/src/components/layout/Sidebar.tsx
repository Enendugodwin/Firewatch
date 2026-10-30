import clsx from "clsx";
import { ChevronsLeft, ChevronsRight, Flame, X } from "lucide-react";
import { NavLink } from "react-router-dom";

import { NAV_SECTIONS } from "@/config/nav";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";
import type { ModuleStatus } from "@/types/api";
import { StatusDot } from "@/components/ui/StatusDot";

const STATUS_TONE: Record<ModuleStatus, "ok" | "info" | "neutral"> = {
  ready: "ok",
  in_progress: "info",
  scaffolded: "neutral",
};

function Logo({ compact }: { compact: boolean }) {
  return (
    <div className={clsx("flex items-center", compact ? "justify-center" : "gap-2.5")}>
      <span
        aria-hidden
        className="flex size-8 shrink-0 items-center justify-center rounded-md border border-fire-medium/40 bg-fire-medium/10"
      >
        <Flame className="size-4 text-fire-medium" />
      </span>
      {!compact ? (
        <span className="min-w-0 leading-none">
          <span className="block truncate text-sm font-semibold tracking-[0.14em] text-ink">
            FIREWATCH <span className="text-fire-medium">X</span>
          </span>
          <span className="mt-1 block truncate text-3xs uppercase tracking-[0.12em] text-faint">
            Fire intelligence
          </span>
        </span>
      ) : null}
    </div>
  );
}

function PhaseProgress() {
  const { data } = useModules();
  const modules = data ?? [];
  const total = modules.length || 11;
  const ready = modules.filter((module) => module.status === "ready").length;

  return (
    <div className="mx-2 mt-2 rounded-md border border-line/70 bg-canvas/50 p-3">
      <div className="flex items-center justify-between">
        <span className="label">Delivery</span>
        <span className="font-mono text-3xs text-muted">Phase 1 / 9</span>
      </div>
      <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-line/70">
        <div
          className="h-full rounded-full bg-fire-medium transition-[width] duration-500"
          style={{ width: `${Math.max(Math.round((ready / total) * 100), 4)}%` }}
        />
      </div>
      <p className="mt-2 text-3xs leading-relaxed text-faint">
        {ready} of {total} modules operational. NASA ingestion starts in Phase 2.
      </p>
    </div>
  );
}

export function Sidebar() {
  const drawerOpen = useUiStore((state) => state.sidebarOpen);
  const collapsedPref = useUiStore((state) => state.sidebarCollapsed);
  const setSidebarOpen = useUiStore((state) => state.setSidebarOpen);
  const toggleCollapsed = useUiStore((state) => state.toggleSidebarCollapsed);
  const { data } = useModules();

  const statusFor = (key: string): ModuleStatus =>
    data?.find((module) => module.key === key)?.status ??
    (key === "settings" ? "in_progress" : "scaffolded");

  return (
    <>
      <div
        aria-hidden
        onClick={() => setSidebarOpen(false)}
        className={clsx(
          "fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity lg:hidden",
          drawerOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-50 flex w-[16.5rem] shrink-0 flex-col border-r border-line/80 bg-sidebar",
          "transition-[transform,width] duration-200 lg:sticky lg:top-0 lg:z-0 lg:h-screen lg:translate-x-0",
          drawerOpen ? "translate-x-0" : "-translate-x-full",
          collapsedPref ? "lg:w-[4.5rem]" : "lg:w-[16.5rem]",
        )}
      >
        {/* Mobile always shows the expanded drawer; `collapsed` applies from lg up. */}
        <div
          className={clsx(
            "flex items-center gap-2 px-3 pb-3 pt-4",
            collapsedPref ? "justify-between lg:flex-col lg:justify-center" : "justify-between",
          )}
        >
          <div className={clsx("min-w-0", collapsedPref && "lg:hidden")}>
            <Logo compact={false} />
          </div>
          {collapsedPref ? (
            <div className="hidden lg:block">
              <Logo compact />
            </div>
          ) : null}

          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close navigation"
              className="rounded p-1.5 text-faint hover:bg-raised hover:text-ink lg:hidden"
            >
              <X className="size-4" aria-hidden />
            </button>
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsedPref ? "Expand navigation" : "Collapse navigation"}
              title={collapsedPref ? "Expand navigation" : "Collapse navigation"}
              className="hidden rounded p-1.5 text-faint hover:bg-raised hover:text-ink lg:block"
            >
              {collapsedPref ? (
                <ChevronsRight className="size-4" aria-hidden />
              ) : (
                <ChevronsLeft className="size-4" aria-hidden />
              )}
            </button>
          </div>
        </div>

        <nav aria-label="Primary navigation" className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title} className="mb-3">
              <div className={clsx("px-2.5 pb-1.5 pt-2", collapsedPref && "lg:hidden")}>
                <span className="label">{section.title}</span>
              </div>
              <ul className="space-y-0.5">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const status = statusFor(item.key);
                  return (
                    <li key={item.key}>
                      <NavLink
                        to={item.to}
                        end={item.to === "/"}
                        onClick={() => setSidebarOpen(false)}
                        title={`${item.label} — ${item.phase}`}
                        className={({ isActive }) =>
                          clsx(
                            "nav-item",
                            isActive && "nav-item-active",
                            collapsedPref && "lg:justify-center lg:px-0",
                          )
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <span className="relative shrink-0">
                              <Icon
                                className={clsx(
                                  "size-4",
                                  isActive ? "text-fire-medium" : "text-faint",
                                )}
                                aria-hidden
                              />
                              {collapsedPref ? (
                                <span className="absolute -right-1.5 -top-1 lg:block">
                                  <StatusDot tone={STATUS_TONE[status]} className="size-1" />
                                </span>
                              ) : null}
                            </span>
                            <span className={clsx("flex-1 truncate", collapsedPref && "lg:hidden")}>
                              {item.label}
                            </span>
                            <span className={clsx(collapsedPref && "lg:hidden")}>
                              <StatusDot
                                tone={STATUS_TONE[status]}
                                label={`${item.label}: ${status}`}
                              />
                            </span>
                          </>
                        )}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className={clsx(collapsedPref && "lg:hidden")}>
          <PhaseProgress />
        </div>

        <div
          className={clsx(
            "mt-2 border-t border-line/70 px-3.5 py-3",
            collapsedPref && "lg:hidden",
          )}
        >
          <p className="text-3xs leading-relaxed text-faint">
            Observations: NASA FIRMS (MODIS, VIIRS SNPP / NOAA-20 / NOAA-21). Detections are
            thermal anomalies, not confirmed wildfires.
          </p>
        </div>
      </aside>
    </>
  );
}
