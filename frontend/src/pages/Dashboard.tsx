import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import GridLayout, { type Layout } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { deletePin, fetchPinData, listPins, updateLayout, type Pin } from "../api/pins";
import ChartRenderer from "../components/ChartRenderer";

const COLS = 12;
const ROW_HEIGHT = 70;

export default function Dashboard() {
  const qc = useQueryClient();
  const {
    data: pins,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["pins"],
    queryFn: listPins,
  });

  const layoutMut = useMutation({
    mutationFn: updateLayout,
    onSettled: () => qc.invalidateQueries({ queryKey: ["pins"] }),
  });

  const delMut = useMutation({
    mutationFn: deletePin,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pins"] }),
  });

  const layout: Layout[] = useMemo(
    () =>
      (pins ?? []).map((p) => ({
        i: p.id,
        x: p.layout.x,
        y: p.layout.y,
        w: p.layout.w,
        h: p.layout.h,
        minW: 3,
        minH: 3,
      })),
    [pins],
  );

  if (isLoading) return <div className="placeholder">Dashboard laden…</div>;
  if (isError) return <div className="placeholder">Fout: {(error as Error).message}</div>;
  if (!pins || pins.length === 0) {
    return (
      <div className="placeholder">
        <h2>Dashboard</h2>
        <p>
          Nog geen vastgezette grafieken. Klik op <strong>📌 Op dashboard zetten</strong> onder een
          grafiek in een chat om er een hier toe te voegen.
        </p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <GridLayout
        className="layout"
        layout={layout}
        cols={COLS}
        rowHeight={ROW_HEIGHT}
        width={getWidth()}
        draggableHandle=".pin-handle"
        onLayoutChange={(items) => {
          // react-grid-layout fires this on every drag tick. We persist after the
          // drag/resize finishes via onDragStop / onResizeStop instead.
          // Keep this as a no-op for now.
          void items;
        }}
        onDragStop={(items) =>
          layoutMut.mutate(items.map((it) => ({ id: it.i, x: it.x, y: it.y, w: it.w, h: it.h })))
        }
        onResizeStop={(items) =>
          layoutMut.mutate(items.map((it) => ({ id: it.i, x: it.x, y: it.y, w: it.w, h: it.h })))
        }
      >
        {pins.map((p) => (
          <div key={p.id} className="pin-tile">
            <PinTile pin={p} onDelete={() => delMut.mutate(p.id)} />
          </div>
        ))}
      </GridLayout>
    </div>
  );
}

function PinTile({ pin, onDelete }: { pin: Pin; onDelete: () => void }) {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["pin-data", pin.id],
    queryFn: () => fetchPinData(pin.id),
    staleTime: 60_000,
  });

  return (
    <>
      <div className="pin-handle">
        <span className="pin-title" title={pin.title}>
          {pin.title}
        </span>
        <span className="pin-actions">
          <button
            onClick={(e) => {
              e.stopPropagation();
              refetch();
            }}
            disabled={isFetching}
            title="Vernieuwen"
          >
            ↻
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (confirm(`"${pin.title}" verwijderen?`)) onDelete();
            }}
            title="Verwijderen"
          >
            ×
          </button>
        </span>
      </div>
      <div className="pin-body">
        {isLoading && <div className="muted">data laden…</div>}
        {isError && <div className="error-banner">Fout: {(error as Error).message}</div>}
        {data && data.rows.length === 0 && <div className="muted">Geen data voor deze query.</div>}
        {data && data.rows.length > 0 && (
          <ChartRenderer spec={pin.chart_spec} rows={data.rows} height={200} />
        )}
      </div>
    </>
  );
}

function getWidth(): number {
  // Crude viewport-based sizing; react-grid-layout doesn't auto-fit width.
  // The dashboard page already has 1.5rem of padding around it.
  if (typeof window === "undefined") return 1200;
  return Math.max(640, window.innerWidth - 24);
}
