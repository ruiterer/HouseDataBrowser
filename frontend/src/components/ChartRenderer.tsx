import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";

export type ChartSpec = {
  type: "line" | "bar" | "scatter" | "heatmap" | "table";
  x?: string;
  y?: string | string[];
  series_by?: string;
  title?: string;
};

type Props = {
  spec: ChartSpec;
  rows: Record<string, any>[];
  height?: number;
};

export default function ChartRenderer({ spec, rows, height = 380 }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    if (spec.type === "table") return;

    const traces = buildTraces(spec, rows);
    const layout: Partial<Plotly.Layout> = {
      title: { text: spec.title ?? "" },
      autosize: true,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { color: "#e6e8ee" },
      margin: { t: 40, r: 10, b: 50, l: 60 },
      xaxis: { title: { text: spec.x ?? "" }, gridcolor: "#232936" },
      yaxis: { gridcolor: "#232936" },
      legend: { bgcolor: "transparent" },
    };
    Plotly.newPlot(ref.current, traces, layout, {
      displaylogo: false,
      responsive: true,
    });
    return () => {
      if (ref.current) Plotly.purge(ref.current);
    };
  }, [spec, rows]);

  if (spec.type === "table") {
    return <div className="chart-empty">Tabelweergave (zie de datatabel hieronder).</div>;
  }
  return <div ref={ref} style={{ width: "100%", height }} />;
}

function buildTraces(spec: ChartSpec, rows: Record<string, any>[]): Plotly.Data[] {
  if (rows.length === 0) return [];
  const x = spec.x ?? "time";
  const yKeys = Array.isArray(spec.y) ? spec.y : spec.y ? [spec.y] : guessNumericColumn(rows, x);

  const groupKey = spec.series_by;
  const groups: Record<string, Record<string, any>[]> = {};
  if (groupKey) {
    for (const r of rows) {
      const k = String(r[groupKey] ?? "(none)");
      (groups[k] ??= []).push(r);
    }
  } else {
    groups["all"] = rows;
  }

  const traces: Plotly.Data[] = [];
  for (const [groupName, groupRows] of Object.entries(groups)) {
    for (const yKey of yKeys) {
      const xs = groupRows.map((r) => r[x]);
      const ys = groupRows.map((r) => coerceNumber(r[yKey]));
      const name = groupKey ? (yKeys.length > 1 ? `${groupName} · ${yKey}` : groupName) : yKey;

      switch (spec.type) {
        case "line":
          traces.push({ x: xs as any, y: ys, type: "scatter", mode: "lines", name });
          break;
        case "bar":
          traces.push({ x: xs as any, y: ys, type: "bar", name });
          break;
        case "scatter":
          traces.push({ x: xs as any, y: ys, type: "scatter", mode: "markers", name });
          break;
        case "heatmap": {
          const z = ys.map((v) => [v]);
          traces.push({ x: xs as any, y: [yKey], z: z as any, type: "heatmap", name });
          break;
        }
      }
    }
  }
  return traces;
}

function guessNumericColumn(rows: Record<string, any>[], xKey: string): string[] {
  for (const k of Object.keys(rows[0] ?? {})) {
    if (k === xKey) continue;
    if (typeof rows[0][k] === "number") return [k];
  }
  return [];
}

function coerceNumber(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
