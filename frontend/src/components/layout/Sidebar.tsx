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

function Wordmark({ compact }: { compact: boolean }) {
  if (compact) {
    return (
      <span
        aria-hidden
        className="flex size-9 items-center justify-center rounded-full border border-line/10 bg-line/[0.03]"
      >
        <Flame className="size-[15px] text-accent" />
      </span>
    );
  }

  return (
    <div className="flex items-center gap-[11px]">
      <span
        aria-hidden
        className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line/10 bg-line/[0.03]"
      >
        <Flame className="size-[15px] text-accent" />
      </span>
      <span className="min-w-0 leading-none">
        <span className="block truncate font-display text-[19px] tracking-[0.01em] text-ink">
          Firewatch <span className="text-accent">X</span>
        </span>
        <span className="mt-[5px] block truncate text-3xs uppercase tracking-[0.2em] text-faint">
          Fire intelligence
        </span>
      </span>
    </div>
  );
}

function DeliveryMeter() {
  const { data } = useModules();
  const modules = data ?? [];
  const total = modules.length || 11;
  const ready = modules.filter((module) => module.status === "ready").length;
  const progress = Math.max(Math.round((ready / total) * 100), 3);

  return (
    <div className="mx-[10px] mb-[10px] rounded-card border border-line/[0.07] bg-line/[0.02] px-[14px] py-[12px]">
      <div className="flex items-baseline justify-between">
        <span className="label">Delivery</span>
        <span className="font-mono text-3xs text-muted">Phase 1 / 9</span>
      </div>
      <div className="mt-[9px] h-[2px] w-full overflow-hidden rounded-full bg-line/10">
        <div
          className="h-full rounded-full bg-accent/80 transition-[width] duration-1000 ease-orbital"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="mt-[9px] text-3xs font-light leading-relaxed text-faint">
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
          "fixed inset-0 z-40 bg-black/70 backdrop-blur-sm transition-opacity duration-150 lg:hidden",
          drawerOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <aside
        className={clsx(
          "glass fixed inset-y-0 left-0 z-50 flex w-[16.5rem] shrink-0 flex-col border-y-0 border-l-0",
          "transition-transform duration-150 lg:sticky lg:top-0 lg:z-0 lg:h-screen lg:translate-x-0",
          drawerOpen ? "translate-x-0" : "-translate-x-full",
          collapsedPref ? "lg:w-[4.5rem]" : "lg:w-[16.5rem]",
        )}
      >
        <div
          className={clsx(
            "flex items-center gap-2 px-[14px] pb-[14px] pt-[18px]",
            collapsedPref ? "justify-between lg:flex-col lg:justify-center" : "justify-between",
          )}
        >
          <div className={clsx("min-w-0", collapsedPref && "lg:hidden")}>
            <Wordmark compact={false} />
          </div>
          {collapsedPref ? (
            <div className="hidden lg:block">
              <Wordmark compact />
            </div>
          ) : null}

          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close navigation"
              className="rounded-full p-1.5 text-faint transition-colors duration-150 hover:bg-line/[0.06] hover:text-ink lg:hidden"
            >
              <X className="size-4" aria-hidden />
            </button>
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsedPref ? "Expand navigation" : "Collapse navigation"}
              title={collapsedPref ? "Expand navigation" : "Collapse navigation"}
              className="hidden rounded-full p-1.5 text-faint transition-colors duration-150 hover:bg-line/[0.06] hover:text-ink lg:block"
            >
              {collapsedPref ? (
                <ChevronsRight className="size-4" aria-hidden />
              ) : (
                <ChevronsLeft className="size-4" aria-hidden />
              )}
            </button>
          </div>
        </div>

        <nav aria-label="Primary navigation" className="min-h-0 flex-1 overflow-y-auto px-[10px] pb-2">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title} className="mb-[14px]">
              <div className={clsx("px-[10px] pb-[6px] pt-[6px]", collapsedPref && "lg:hidden")}>
                <span className="label">{section.title}</span>
              </div>
              <ul className="space-y-[1px]">
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
                                  "nav-icon size-[15px]",
                                  isActive ? "text-accent" : "text-faint",
                                )}
                                aria-hidden
                              />
                              {collapsedPref ? (
                                <span className="absolute -right-[3px] -top-[2px] hidden lg:block">
                                  <StatusDot tone={STATUS_TONE[status]} className="size-[4px]" />
                                </span>
                              ) : null}
                            </span>
                            <span
                              className={clsx(
                                "flex-1 truncate tracking-[0.01em]",
                                collapsedPref && "lg:hidden",
                              )}
                            >
                              {item.label}
                            </span>
                            <span className={clsx(collapsedPref && "lg:hidden")}>
                              {status === "scaffolded" ? null : (
                                <StatusDot
                                  tone={STATUS_TONE[status]}
                                  label={`${item.label}: ${status}`}
                                />
                              )}
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
          <DeliveryMeter />
        </div>

        <div
          className={clsx(
            "border-t border-line/[0.07] px-[16px] py-[14px]",
            collapsedPref && "lg:hidden",
          )}
        >
          <p className="text-3xs font-light leading-relaxed text-faint">
            Observations: NASA FIRMS (MODIS, VIIRS SNPP / NOAA-20 / NOAA-21). Detections are thermal
            anomalies, not confirmed wildfires.
          </p>
        </div>
      </aside>
    </>
  );
}
