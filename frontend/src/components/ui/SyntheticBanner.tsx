import { FlaskConical } from "lucide-react";

/**
 * Synthetic-data banner. Any view that can display fixture rows must show this:
 * labelled fixtures exist to exercise the pipeline and are never NASA data.
 */
export function SyntheticBanner({
  count,
  total,
}: {
  count: number;
  total: number;
}) {
  if (!count) return null;
  const allSynthetic = count === total;

  return (
    <div className="mb-[12px] flex items-start gap-[10px] rounded-card border border-warn/25 bg-warn/[0.05] px-[18px] py-[12px]">
      <FlaskConical className="mt-[1px] size-3.5 shrink-0 text-warn" aria-hidden />
      <div className="text-2xs font-light leading-relaxed text-muted">
        <span className="text-ink">
          {allSynthetic ? "Demo data only." : "Mixed provenance."}
        </span>{" "}
        {allSynthetic ? (
          <>
            All {count} stored observations come from the labelled synthetic fixture, not NASA
            FIRMS. They exercise ingestion, normalization, matching and event grouping end to end
            and must not be read as observed fire activity.
          </>
        ) : (
          <>
            {count} of {total} stored observations are synthetic fixture rows. NASA observations and
            fixture rows are never harmonized together.
          </>
        )}
      </div>
    </div>
  );
}
