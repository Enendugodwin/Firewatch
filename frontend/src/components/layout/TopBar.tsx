import { Contrast, ExternalLink, Menu, Moon, Search, Settings2, ShieldCheck, UserRound } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { NAV_ITEMS } from "@/config/nav";
import { useSystemStatus } from "@/lib/queries";
import { useUiStore } from "@/store/ui";
import { Badge } from "@/components/ui/Badge";
import { Popover } from "@/components/ui/Popover";
import { DateRangeControl } from "./DateRangeControl";
import { FreshnessIndicator } from "./FreshnessIndicator";
import { NotificationsMenu } from "./NotificationsMenu";

const iconButton =
  "inline-flex size-8 items-center justify-center rounded-full border border-line/10 bg-line/[0.03] text-muted transition-colors duration-150 hover:border-line/20 hover:text-ink";

function ProfileMenu() {
  const { data } = useSystemStatus();

  return (
    <Popover
      label="Profile and session"
      widthClass="w-[19rem]"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          id={id}
          onClick={toggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-label="Profile and session"
          className={iconButton}
        >
          <UserRound className="size-[15px]" aria-hidden />
        </button>
      )}
    >
      {(close) => (
        <div className="p-[18px]">
          <div className="flex items-center gap-[10px]">
            <span className="flex size-9 items-center justify-center rounded-full border border-line/10 font-mono text-3xs text-muted">
              OP
            </span>
            <div className="min-w-0">
              <div className="truncate text-xs text-ink">Local operator</div>
              <div className="text-2xs font-light text-faint">Unauthenticated session</div>
            </div>
          </div>

          <div className="mt-[14px] flex items-center justify-between rounded-control border border-line/[0.08] px-[10px] py-[7px]">
            <span className="inline-flex items-center gap-1.5 text-2xs font-light text-muted">
              <ShieldCheck className="size-3" aria-hidden /> Role
            </span>
            <Badge tone="neutral">Viewer</Badge>
          </div>

          <p className="mt-2 text-2xs font-light leading-relaxed text-faint">
            Authentication and role-based access control arrive with the security phase. Until then
            this console is open and must not be exposed to an untrusted network.
          </p>

          <div className="mt-[14px] space-y-[2px] border-t border-line/[0.07] pt-[10px]">
            <Link
              to="/settings"
              onClick={close}
              className="flex items-center gap-2 rounded-control px-2 py-[7px] text-xs font-light text-muted transition-colors duration-150 hover:bg-line/[0.05] hover:text-ink"
            >
              <Settings2 className="size-3.5 text-faint" aria-hidden />
              Settings &amp; administration
            </Link>
            <a
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-control px-2 py-[7px] text-xs font-light text-muted transition-colors duration-150 hover:bg-line/[0.05] hover:text-ink"
            >
              <ExternalLink className="size-3.5 text-faint" aria-hidden />
              API documentation
            </a>
          </div>

          <div className="mt-[10px] flex items-center justify-between border-t border-line/[0.07] pt-[10px] text-3xs text-faint">
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
      className={iconButton}
    >
      {isContrast ? (
        <Contrast className="size-[15px] text-accent" aria-hidden />
      ) : (
        <Moon className="size-[15px]" aria-hidden />
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
    <header className="glass sticky top-0 z-30 flex h-14 items-center gap-2 border-x-0 border-t-0 px-3 sm:px-[22px]">
      <button
        type="button"
        onClick={() => setSidebarOpen(true)}
        aria-label="Open navigation"
        className={`${iconButton} shrink-0 lg:hidden`}
      >
        <Menu className="size-[15px]" aria-hidden />
      </button>

      <div className="hidden min-w-0 items-center gap-2 sm:flex">
        <span className="label shrink-0">Firewatch X</span>
        <span className="text-line/25">/</span>
        <span className="truncate text-xs font-light text-ink">{current?.label ?? "Not found"}</span>
      </div>

      <div className="flex min-w-0 flex-1 justify-center px-1">
        <button
          type="button"
          onClick={() => setCommandOpen(true)}
          aria-label="Search modules"
          className="group flex h-8 w-8 shrink-0 items-center justify-center gap-2 rounded-full border border-line/10 bg-line/[0.03] px-0 text-left text-2xs font-light text-faint transition-colors duration-150 hover:border-line/20 hover:text-muted sm:w-full sm:max-w-sm sm:justify-start sm:px-[12px]"
        >
          <Search className="size-3.5 shrink-0" aria-hidden />
          <span className="hidden flex-1 truncate sm:block">Search modules</span>
          <kbd className="hidden items-center rounded-full border border-line/10 px-[6px] py-[1px] font-mono text-3xs text-faint sm:flex">
            Ctrl K
          </kbd>
        </button>
      </div>

      <div className="flex shrink-0 items-center gap-[6px]">
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
