import type { ChartSpec } from "../components/ChartRenderer";
import { apiUrl } from "../base";

export type Pin = {
  id: string;
  title: string;
  query: string;
  chart_spec: ChartSpec;
  layout: { x: number; y: number; w: number; h: number };
  created_at: string;
  updated_at: string;
};

export type PinData = {
  columns: string[];
  rows: Record<string, any>[];
  row_count: number;
};

export async function listPins(): Promise<Pin[]> {
  const res = await fetch(apiUrl("/api/pins"));
  if (!res.ok) throw new Error("listPins failed");
  return res.json();
}

export async function createPin(input: {
  title: string;
  query: string;
  chart_spec: ChartSpec;
}): Promise<Pin> {
  const res = await fetch(apiUrl("/api/pins"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error("createPin failed");
  return res.json();
}

export async function deletePin(id: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/pins/${id}`), { method: "DELETE" });
  if (!res.ok) throw new Error("deletePin failed");
}

export async function updateLayout(
  items: { id: string; x: number; y: number; w: number; h: number }[],
): Promise<void> {
  const res = await fetch(apiUrl("/api/pins/layout"), {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(items),
  });
  if (!res.ok) throw new Error("updateLayout failed");
}

export async function fetchPinData(id: string): Promise<PinData> {
  const res = await fetch(apiUrl(`/api/pins/${id}/data`));
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`fetchPinData failed: ${detail}`);
  }
  return res.json();
}
