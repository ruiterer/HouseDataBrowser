import { useState } from "react";

type Props = {
  query: string;
  events?: { name: string; preview: string }[];
};

export default function QueryDebugPanel({ query, events }: Props) {
  const [open, setOpen] = useState(false);
  if (!query && (!events || events.length === 0)) return null;
  return (
    <div className="debug-panel">
      <button className="debug-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? "▾" : "▸"} details
      </button>
      {open && (
        <div className="debug-body">
          {query && (
            <div className="debug-section">
              <div className="debug-label">InfluxQL</div>
              <pre>{query}</pre>
              <button onClick={() => navigator.clipboard.writeText(query)}>Kopiëren</button>
            </div>
          )}
          {events && events.length > 0 && (
            <div className="debug-section">
              <div className="debug-label">Stappen</div>
              <ol className="trace-list">
                {events.map((e, i) => (
                  <li key={i}>
                    <code>{e.name}</code> {e.preview}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
