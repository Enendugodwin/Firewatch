import { Contrast, ExternalLink, Menu, Moon, Search, Settings2, ShieldCheck, UserRound } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { NAV_ITEMS } from "@/config/nav";
import { useSystemStatus } from "@/lib/queries";
import { useUiStore } from "@/store/ui";
import { Badge } from "@/components/ui/Badge";
import { Popover } from "@/components/ui/Popover";
import { StatusDot } from "@/components/ui/StatusDot";
import { DateRangeControl } from "./DateRangeControl";
import { FreshnessIndicator } from "./FreshnessIndicator";
import { NotificationsMenu } from "./NotificationsMenu";

function ProfileMenu() {
  const { data } = useSystemStatus();

  return (
    <Popover
      label="Profile and session"
      widthClass="w-72"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          id={id}
          onClick={toggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-label="Profile and session"
          className="inline-flex size-8 items-center justify-center rounded-md border border-line bg-raised/50 text-muted transition-colors hover:text-ink"
        >
          <UserRound className="size-4" aria-hidden />
        </button>
      )}
    >
      {(close) => (
        <div className="p-3.5">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-full border border-line bg-raised font-mono text-2xs text-muted">
              OP
            </span>
            <div className="min-w-0">
              <div className="truncate text-xs font-medium text-ink">Local operator</div>
              <div className="text-2xs text-faint">Unauthenticated session</div>
            </div>
          </div>

          <div className="mt-3 flex items-center justify-between rounded border border-line/70 bg-canvas/50 px-2.5 py-2">
            <span className="inline-flex items-center gap-1.5 text-2xs text-muted">
              <ShieldCheck className="size-3" aria-hidden /> Role
            </span>
            <Badge tone="neutral">VIEWER</Badge>
          </div>

          <p className="mt-2 text-2xs leading-relaxed text-faint">
            Authentication and role-based access control arrive with the security phase. Until then
            this console is open and must not be exposed to an untrusted network.
          </p>

          <div className="mt-3 space-y-1 border-t border-line/70 pt-2.5">
            <Link
              to="/settings"
              onClick={close}
              className="flex items-center gap-2 rounded px-1.5 py-1.5 text-xs text-muted hover:bg-raised/60 hover:text-ink"
            >
              <Settings2 className="size-3.5 text-faint" aria-hidden />
              Settings &amp; administration
            </Link>
            <a
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded px-1.5 py-1.5 text-xs text-muted hover:bg-raised/60 hover:text-ink"
            >
              <ExternalLink className="size-3.5 text-faint" aria-hidden />
              API documentation
            </a>
          </div>

          <div className="mt-2 flex items-center justify-between border-t border-line/70 pt-2.5 text-2xs text-faint">
            <span>API {data?.app_version ?? "—"}</span>
            <span className="font-mono">{data?.environment ?? "—"}</span>
          </div>
        </div>
      )}
    </Popover>
  );
}

function ThemeToggle() {
  const theme = useUiStore((state) => state.theme);
  const toggleTheme = useUiStore((state) => state.toggleTheme);
  const isContrast = theme === "contrast";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isContrast ? "Switch to standard dark theme" : "Switch to high-contrast theme"}
      title={isContrast ? "High contrast: on" : "High contrast: off"}
      className="inline-flex size-8 items-center justify-center rounded-md border border-line bg-raised/50 text-muted transition-colors hover:text-ink"
    >
      {isContrast ? (
        <Contrast className="size-4 text-geo" aria-hidden />
      ) : (
        <Moon className="size-4" aria-hidden />
      )}
    </button>
  );
}

export function TopBar() {
  const setSidebarOpen = useUiStore((state) => state.setSidebarOpen);
  const setCommandOpen = useUiStore((state) => state.setCommandOpen);
  const location = useLocation();
  const current = NAV_ITEMS.find((item) =>
    item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to),
  );

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-line/80 bg-canvas/85 px-3 backdrop-blur sm:px-4">
      <button
        type="button"
        onClick={() => setSidebarOpen(true)}
        aria-label="Open navigation"
        className="inline-flex size-8 items-center justify-center rounded-md border border-line bg-raised/50 text-muted hover:text-ink lg:hidden"
      >
        <Menu className="size-4" aria-hidden />
      </button>

      <div className="hidden min-w-0 items-baseline gap-2 sm:flex">
        <span className="label shrink-0">FIREWATCH X</span>
        <span className="text-faint">/</span>
        <span className="truncate text-xs text-ink">{current?.label ?? "Not found"}</span>
      </div>

      <div className="flex min-w-0 flex-1 justify-center px-1">
        <button
          type="button"
          onClick={() => setCommandOpen(true)}
          aria-label="Search modules"
          className="group flex h-8 w-8 shrink-0 items-center justify-center gap-2 rounded-md border border-line bg-raised/40 px-0 text-left text-2xs text-faint transition-colors hover:border-faint/60 hover:text-muted sm:w-full sm:max-w-sm sm:justify-start sm:px-2.5"
        >
          <Search className="size-3.5 shrink-0" aria-hidden />
          <span className="hidden flex-1 truncate sm:block">Search modules</span>
          <kbd className="hidden items-center gap-0.5 rounded border border-line bg-canvas px-1 py-0.5 font-mono text-3xs text-faint sm:flex">
            Ctrl K
          </kbd>
        </button>
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <div className="hidden md:block">
          <DateRangeControl />
        </div>
        <FreshnessIndicator />
        <NotificationsMenu />
        <div className="hidden sm:block">
          <ThemeToggle />
        </div>
        <ProfileMenu />
      </div>
    </header>
  );
}

export function DataStatusDot() {
  const { data } = useSystemStatus();
  const tone = !data ? "neutral" : data.database.connected ? "ok" : "danger";
  return <StatusDot tone={tone} pulse={tone === "ok"} />;
}
