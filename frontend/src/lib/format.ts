/** Formatting for measurements. Counts are detections unless labelled otherwise. */

const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return integer.format(value);
}

export function formatFrp(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${decimal.format(value)} MW`;
}

export function formatDistance(metres: number | null | undefined): string {
  if (metres === null || metres === undefined) return "—";
  if (metres < 1000) return `${integer.format(Math.round(metres))} m`;
  return `${decimal.format(metres / 1000)} km`;
}

export function formatDeltaSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

export function formatCoordinate(value: number): string {
  return value.toFixed(4);
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(3);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}
