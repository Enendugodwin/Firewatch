import { Compass, MoveLeft } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <span className="mb-4 flex size-11 items-center justify-center rounded-full border border-line bg-raised/60 text-faint">
        <Compass className="size-5" aria-hidden />
      </span>
      <h1 className="text-lg font-semibold text-ink">No such view</h1>
      <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-muted">
        That route does not correspond to a FIREWATCH X module. Use the navigation or the command
        palette (Ctrl K) to reach a workspace.
      </p>
      <Link
        to="/"
        className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-line bg-raised px-3 py-1.5 text-xs text-ink hover:border-faint/70"
      >
        <MoveLeft className="size-3.5" aria-hidden />
        Back to overview
      </Link>
    </div>
  );
}
