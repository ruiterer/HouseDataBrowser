import { apiUrl } from "../base";
export type FieldKey = { name: string; type: string };

export type Measurement = {
  measurement: string;
  description: string;
  tag_keys: string[];
  field_keys: FieldKey[];
  tag_values: Record<string, string[]>;
  updated_at: string;
};

export type SchemaSummary = {
  measurements: Measurement[];
  last_refresh: string | null;
  last_error: string | null;
  is_refreshing: boolean;
};

export async function fetchSchema(): Promise<SchemaSummary> {
  const res = await fetch(apiUrl("/api/schema"));
  if (!res.ok) throw new Error(`fetchSchema failed: ${res.status}`);
  return res.json();
}

export async function updateDescription(
  measurement: string,
  description: string,
): Promise<Measurement> {
  const res = await fetch(apiUrl(`/api/schema/${encodeURIComponent(measurement)}/description`), {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error(`updateDescription failed: ${res.status}`);
  return res.json();
}

export async function triggerRefresh(): Promise<{ status: string }> {
  const res = await fetch(apiUrl("/api/schema/refresh"), { method: "POST" });
  if (!res.ok) throw new Error(`triggerRefresh failed: ${res.status}`);
  return res.json();
}
