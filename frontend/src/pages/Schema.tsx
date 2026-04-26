import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchSchema,
  triggerRefresh,
  updateDescription,
  type Measurement,
} from "../api/schema";

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "nooit";
  const d = new Date(iso);
  return d.toLocaleString("nl-NL");
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

  if (isLoading) return <div className="placeholder">Schema laden…</div>;
  if (isError) return <div className="placeholder">Fout: {(error as Error).message}</div>;
  if (!data) return null;

  return (
    <div className="schema-page">
      <header className="schema-header">
        <h2>Schema ({data.measurements.length} metingen)</h2>
        <div className="schema-meta">
          <span>laatst vernieuwd: {formatTime(data.last_refresh)}</span>
          {data.is_refreshing && <span className="refreshing">vernieuwen…</span>}
          {data.last_error && <span className="error">laatste fout: {data.last_error}</span>}
          <button
            onClick={() => refreshMut.mutate()}
            disabled={data.is_refreshing || refreshMut.isPending}
          >
            Nu vernieuwen
          </button>
        </div>
        <input
          type="text"
          className="schema-filter"
          placeholder="Filter op meting / tag / veld / beschrijving…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </header>

      {data.measurements.length === 0 && (
        <div className="placeholder">
          Nog geen metingen gevonden. De eerste vernieuwing draait bij het starten;
          als de InfluxDB-verbinding nog niet werkt, los dat dan eerst op (zie de
          status-badge rechtsboven).
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
  const navigate = useNavigate();
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

  function askAboutField(fieldName: string) {
    const prefill = `Laat de waarde van \`${fieldName}\` op meting \`${m.measurement}\` zien voor de afgelopen 30 dagen.`;
    navigate("/", { state: { prefill, freshConversation: true } });
  }

  return (
    <li className={`schema-card ${open ? "open" : ""}`}>
      <div className="schema-card-header" onClick={() => setOpen((v) => !v)}>
        <span className="caret">{open ? "▾" : "▸"}</span>
        <span className="name">{m.measurement}</span>
        <span className="counts">
          {m.tag_keys.length} tags · {m.field_keys.length} velden
        </span>
      </div>
      {open && (
        <div className="schema-card-body" onClick={(e) => e.stopPropagation()}>
          <div className="schema-row">
            <label>Beschrijving</label>
            {editing ? (
              <div className="edit-row">
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={3}
                  placeholder={`Wat is ${m.measurement}? (deze hint gaat naar de LLM)`}
                />
                <div className="edit-actions">
                  <button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
                    {saveMut.isPending ? "Opslaan…" : "Opslaan"}
                  </button>
                  <button
                    onClick={() => {
                      setEditing(false);
                      setDraft(m.description);
                    }}
                  >
                    Annuleren
                  </button>
                </div>
              </div>
            ) : (
              <div className="display-row">
                <p className="description">
                  {m.description || <em className="muted">Geen beschrijving.</em>}
                </p>
                <button onClick={() => setEditing(true)}>Bewerken</button>
              </div>
            )}
          </div>

          <div className="schema-row">
            <label>Veldsleutels</label>
            <ul className="key-list">
              {m.field_keys.map((fk) => (
                <li key={fk.name}>
                  <button
                    className="field-pick"
                    onClick={() => askAboutField(fk.name)}
                    title={`Stel een vraag over ${fk.name} in een nieuw gesprek`}
                  >
                    <code>{fk.name}</code> <span className="muted">({fk.type})</span>
                    <span className="field-pick-hint">💬</span>
                  </button>
                </li>
              ))}
              {m.field_keys.length === 0 && <li className="muted">geen</li>}
            </ul>
          </div>

          <div className="schema-row">
            <label>Tagsleutels</label>
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
              {m.tag_keys.length === 0 && <li className="muted">geen</li>}
            </ul>
          </div>
        </div>
      )}
    </li>
  );
}
