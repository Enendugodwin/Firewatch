import type { Observation } from "@/types/api";

/** FIRMS gymbal code: D = day, N = night. */
const DAYNIGHT_LABELS: Record<string, string> = { D: "Day", N: "Night" };

/**
 * Provenance rows for a single detection, shared by the map inspection panel and
 * the calendar drill-down. Values are read straight from the stored observation;
 * nothing is inferred except the day/night label.
 */
export function provenanceRows(observation: Observation): { label: string; value: string }[] {
  const rows: { label: string; value: string }[] = [
    {
      label: "Coordinates",
      value: `${observation.latitude.toFixed(4)}, ${observation.longitude.toFixed(4)}`,
    },
    {
      label: "Acquired (UTC)",
      value: observation.acquired_at.replace("T", " ").slice(0, 16) + "Z",
    },
    { label: "Sensor / satellite", value: `${observation.sensor} · ${observation.satellite}` },
    {
      label: "Confidence",
      value:
        observation.confidence_raw !== null
          ? `${observation.confidence_raw} (${observation.confidence_category ?? "n/a"})`
          : (observation.confidence_category ?? "n/a"),
    },
    {
      label: "Brightness",
      value:
        observation.brightness_temperature !== null
          ? `${observation.brightness_temperature.toFixed(1)} K · ${observation.brightness_channel ?? "channel n/a"}`
          : "n/a",
    },
    {
      label: "FRP",
      value: observation.frp_mw !== null ? `${observation.frp_mw.toFixed(2)} MW` : "n/a",
    },
    {
      label: "Scan / track",
      value:
        observation.scan_km !== null && observation.track_km !== null
          ? `${observation.scan_km.toFixed(2)} × ${observation.track_km.toFixed(2)} km`
          : "n/a",
    },
    {
      label: "Day / night",
      value: DAYNIGHT_LABELS[(observation.daynight ?? "").toUpperCase()] ?? "n/a",
    },
    {
      label: "Product",
      value: `${observation.source_product}${
        observation.processing_version ? ` · ${observation.processing_version}` : ""
      }`,
    },
    { label: "Record id", value: observation.source_record_id },
  ];
  return rows;
}
