import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchSchema,
  triggerRefresh,
  updateDescription,
  type Measurement,
} from "../api/schema";

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const d = new Date(iso);
  return d.toLocaleString();
}

export default function Schema() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState("");
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["schema"],
    queryFn: fetchSchema,
    refetchInterval: (q) => (q.state.data?.is_refreshing ? 2000 : 30_000),
  });

  const refreshMut = useMutation({
    mutationFn: triggerRefresh,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schema"] }),
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const f = filter.trim().toLowerCase();
    if (!f) return data.measurements;
    return data.measurements.filter(
      (m) =>
        m.measurement.toLowerCase().includes(f) ||
        m.description.toLowerCase().includes(f) ||
        m.tag_keys.some((t) => t.toLowerCase().includes(f)) ||
        m.field_keys.some((fk) => fk.name.toLowerCase().includes(f)),
    );
  }, [data, filter]);

  if (isLoading) return <div className="placeholder">Loading schema…</div>;
  if (isError) return <div className="placeholder">Error: {(error as Error).message}</div>;
  if (!data) return null;

  return (
    <div className="schema-page">
      <header className="schema-header">
        <h2>Schema ({data.measurements.length} measurements)</h2>
        <div className="schema-meta">
          <span>last refresh: {formatTime(data.last_refresh)}</span>
          {data.is_refreshing && <span className="refreshing">refreshing…</span>}
          {data.last_error && <span className="error">last error: {data.last_error}</span>}
          <button
            onClick={() => refreshMut.mutate()}
            disabled={data.is_refreshing || refreshMut.isPending}
          >
            Refresh now
          </button>
        </div>
        <input
          type="text"
          className="schema-filter"
          placeholder="Filter by measurement / tag / field / description…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </header>

      {data.measurements.length === 0 && (
        <div className="placeholder">
          No measurements discovered yet. The first refresh runs on startup; if your
          InfluxDB connection isn't working yet, fix that first (see the health badge).
        </div>
      )}

      <ul className="schema-list">
        {filtered.map((m) => (
          <MeasurementCard key={m.measurement} m={m} />
        ))}
      </ul>
    </div>
  );
}

function MeasurementCard({ m }: { m: Measurement }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(m.description);
  const [editing, setEditing] = useState(false);

  const saveMut = useMutation({
    mutationFn: () => updateDescription(m.measurement, draft),
    onSuccess: () => {
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["schema"] });
    },
  });

  return (
    <li className={`schema-card ${open ? "open" : ""}`}>
      <div className="schema-card-header" onClick={() => setOpen((v) => !v)}>
        <span className="caret">{open ? "▾" : "▸"}</span>
        <span className="name">{m.measurement}</span>
        <span className="counts">
          {m.tag_keys.length} tags · {m.field_keys.length} fields
        </span>
      </div>
      {open && (
        <div className="schema-card-body" onClick={(e) => e.stopPropagation()}>
          <div className="schema-row">
            <label>Description</label>
            {editing ? (
              <div className="edit-row">
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={3}
                  placeholder={`What is ${m.measurement}? (this hint goes to the LLM)`}
                />
                <div className="edit-actions">
                  <button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
                    {saveMut.isPending ? "Saving…" : "Save"}
                  </button>
                  <button
                    onClick={() => {
                      setEditing(false);
                      setDraft(m.description);
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="display-row">
                <p className="description">
                  {m.description || <em className="muted">No description.</em>}
                </p>
                <button onClick={() => setEditing(true)}>Edit</button>
              </div>
            )}
          </div>

          <div className="schema-row">
            <label>Field keys</label>
            <ul className="key-list">
              {m.field_keys.map((fk) => (
                <li key={fk.name}>
                  <code>{fk.name}</code> <span className="muted">({fk.type})</span>
                </li>
              ))}
              {m.field_keys.length === 0 && <li className="muted">none</li>}
            </ul>
          </div>

          <div className="schema-row">
            <label>Tag keys</label>
            <ul className="key-list">
              {m.tag_keys.map((tk) => {
                const sample = m.tag_values[tk];
                return (
                  <li key={tk}>
                    <code>{tk}</code>
                    {sample && sample.length > 0 && (
                      <span className="muted"> — {sample.slice(0, 8).join(", ")}{sample.length > 8 ? "…" : ""}</span>
                    )}
                  </li>
                );
              })}
              {m.tag_keys.length === 0 && <li className="muted">none</li>}
            </ul>
          </div>
        </div>
      )}
    </li>
  );
}
