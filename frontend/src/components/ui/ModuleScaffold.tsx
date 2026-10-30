import { AlertTriangle, Database, Route } from "lucide-react";
import type { ReactNode } from "react";

import { MODULE_ENDPOINTS } from "@/config/contracts";
import { findNavItemByKey, DEFAULT_STATUS } from "@/config/nav";
import { useModules } from "@/lib/queries";
import type { ModuleStatusItem } from "@/types/api";
import { Panel } from "@/components/ui/Panel";
import { PageHeader, ModuleStatusPill, PhaseBadge } from "@/components/ui/ModuleStatus";
import { PendingDataNotice } from "@/components/ui/EmptyState";

/**
 * Consistent shell for a module that is scaffolded but not yet analytical.
 * Status and planned capabilities come from the API registry so the UI cannot
 * drift from the backend into claiming a feature exists.
 */
export function ModuleScaffold({
  moduleKey,
  extra,
  children,
  requirements,
}: {
  moduleKey: string;
  /** Extra content rendered above the pending-data notice. */
  extra?: ReactNode;
  /** Replace the default pending-data notice. */
  children?: ReactNode;
  requirements?: string[];
}) {
  const navItem = findNavItemByKey(moduleKey);
  const { data } = useModules();
  const module: ModuleStatusItem | undefined = data?.find((item) => item.key === moduleKey);

  const label = module?.label ?? navItem?.label ?? moduleKey;
  const phase = module?.phase ?? navItem?.phase ?? "Phase 1";
  const status = module?.status ?? DEFAULT_STATUS[moduleKey] ?? "scaffolded";
  const endpoints = MODULE_ENDPOINTS[moduleKey] ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="FIREWATCH X module"
        title={label}
        description={module?.summary}
        status={status}
        phase={phase}
      />

      {extra}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {children ?? <PendingDataNotice phase={phase} />}

          <Panel
            title="Planned capabilities"
            subtitle={`What this module delivers in ${phase}, per the product specification.`}
          >
            {module?.planned?.length ? (
              <ul className="space-y-2">
                {module.planned.map((capability) => (
                  <li key={capability} className="flex gap-2.5 text-xs leading-relaxed text-muted">
                    <span className="mt-1.5 size-1 shrink-0 rounded-full bg-fire-medium/70" />
                    <span>{capability}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-faint">Capability list unavailable.</p>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel
            title="API contract"
            subtitle="Published now so the surface is fixed before implementation."
            bodyClassName="p-0"
          >
            <ul className="divide-y divide-line/60">
              {endpoints.map((endpoint) => (
                <li key={`${endpoint.method} ${endpoint.path}`} className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-3xs uppercase text-muted">
                      {endpoint.method}
                    </span>
                    <code className="truncate font-mono text-2xs text-ink">{endpoint.path}</code>
                  </div>
                  <p className="mt-1 text-2xs text-faint">{endpoint.purpose}</p>
                </li>
              ))}
            </ul>
            <div className="flex items-start gap-2 border-t border-line/60 bg-canvas/40 px-4 py-2.5">
              <Route className="mt-0.5 size-3.5 shrink-0 text-faint" aria-hidden />
              <p className="text-2xs leading-relaxed text-faint">
                These routes currently return <code className="text-muted">501 not_implemented</code>{" "}
                with the phase that will build them.
              </p>
            </div>
          </Panel>

          <Panel
            title="Module state"
            subtitle="Reported by /api/v1/system/modules."
            actions={<ModuleStatusPill status={status} />}
          >
            <dl className="space-y-2 text-xs">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-faint">Delivery phase</dt>
                <dd>
                  <PhaseBadge phase={phase} />
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-faint">Data source</dt>
                <dd className="text-muted">NASA FIRMS</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-faint">Storage</dt>
                <dd className="inline-flex items-center gap-1.5 text-muted">
                  <Database className="size-3" aria-hidden /> PostgreSQL / PostGIS
                </dd>
              </div>
            </dl>
          </Panel>

          {requirements?.length ? (
            <Panel
              title="Before this module can show data"
              actions={<AlertTriangle className="size-3.5 text-warn" aria-hidden />}
            >
              <ul className="space-y-1.5">
                {requirements.map((requirement) => (
                  <li key={requirement} className="text-2xs leading-relaxed text-muted">
                    {requirement}
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}
