import { Bell, BellRing } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Popover } from "@/components/ui/Popover";
import type { Tone } from "@/components/ui/Badge";
import { useSystemStatus } from "@/lib/queries";

interface Notice {
  id: string;
  title: string;
  detail: string;
  tone: Tone;
  to?: string;
}

/**
 * Notices are derived from real system state, never from invented events. They
 * are the honest subset of what the alert engine will emit in Phase 7.
 */
function buildNotices(status: ReturnType<typeof useSystemStatus>["data"]): Notice[] {
  if (!status) return [];

  const notices: Notice[] = [];

  if (!status.data.firms_configured) {
    notices.push({
      id: "firms-key",
      title: "NASA FIRMS key not configured",
      detail:
        "Set FIRMS_MAP_KEY in the backend environment. Without it no observations can be retrieved.",
      tone: "warn",
      to: "/settings",
    });
  }

  if (status.data.freshness === "no_data") {
    notices.push({
      id: "no-data",
      title: "No observations ingested yet",
      detail:
        "Ingestion ships in Phase 2. Every module reports an empty state until then — no sample data is used.",
      tone: "info",
      to: "/settings",
    });
  }

  if (!status.database.connected) {
    notices.push({
      id: "db-down",
      title: "Database unreachable",
      detail: status.database.error ?? "The analytics database did not respond to the probe.",
      tone: "danger",
      to: "/settings",
    });
  } else if (!status.database.postgis && status.database.dialect !== "sqlite") {
    notices.push({
      id: "postgis-missing",
      title: "PostGIS extension missing",
      detail: "Spatial queries require the postgis extension on the configured database.",
      tone: "warn",
      to: "/settings",
    });
  }

  notices.push({
    id: "phase",
    title: `Phase ${status.phase} — ${status.phase_name}`,
    detail: "Foundation is built. NASA integration, harmonization and the burning calendar follow.",
    tone: "neutral",
    to: "/settings",
  });

  return notices;
}

export function NotificationsMenu() {
  const { data } = useSystemStatus();
  const notices = useMemo(() => buildNotices(data), [data]);
  const actionable = notices.filter((notice) => notice.tone === "warn" || notice.tone === "danger");

  return (
    <Popover
      label="Notifications"
      widthClass="w-[20rem]"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          id={id}
          onClick={toggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-label={`Notifications (${notices.length})`}
          className="relative inline-flex size-8 items-center justify-center rounded-full border border-line/10 bg-line/[0.03] text-muted transition-colors duration-150 hover:border-line/20 hover:text-ink"
        >
          {actionable.length > 0 ? (
            <BellRing className="size-[15px]" aria-hidden />
          ) : (
            <Bell className="size-[15px]" aria-hidden />
          )}
          {notices.length > 0 ? (
            <span className="absolute -right-[3px] -top-[3px] flex size-[15px] items-center justify-center rounded-full bg-accent font-mono text-[9px] font-semibold text-[#05070F]">
              {notices.length}
            </span>
          ) : null}
        </button>
      )}
    >
      {(close) => (
        <div>
          <div className="flex items-center justify-between border-b border-line/[0.07] px-[14px] py-[11px]">
            <span className="label">System notices</span>
            <Badge tone="neutral">{notices.length}</Badge>
          </div>
          <ul className="max-h-[18rem] overflow-y-auto">
            {notices.map((notice) => (
              <li key={notice.id} className="border-b border-line/[0.05] last:border-0">
                <Link
                  to={notice.to ?? "/settings"}
                  onClick={close}
                  className="block px-[14px] py-[11px] transition-colors duration-150 hover:bg-line/[0.04]"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs text-ink">{notice.title}</span>
                    <Badge tone={notice.tone}>{notice.tone === "danger" ? "error" : notice.tone}</Badge>
                  </div>
                  <p className="mt-1 text-2xs font-light leading-relaxed text-muted">
                    {notice.detail}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Popover>
  );
}
