import { useMemo } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";

type Props = {
  columns: string[];
  rows: Record<string, any>[];
  maxRows?: number;
};

export default function DataTable({ columns, rows, maxRows = 200 }: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const cols: ColumnDef<Record<string, any>>[] = useMemo(
    () => columns.map((c) => ({ id: c, header: c, accessorKey: c })),
    [columns],
  );
  const visibleRows = useMemo(() => rows.slice(0, maxRows), [rows, maxRows]);
  const table = useReactTable({
    data: visibleRows,
    columns: cols,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  function downloadCsv() {
    const csv = toCsv(columns, rows);
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "result.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  if (rows.length === 0) {
    return <div className="muted">Geen rijen.</div>;
  }
  return (
    <div className="table-wrap">
      <div className="table-meta">
        <span className="muted">
          {visibleRows.length.toLocaleString("nl-NL")} van {rows.length.toLocaleString("nl-NL")}{" "}
          rijen weergegeven
        </span>
        <button onClick={downloadCsv}>CSV downloaden</button>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th key={h.id} onClick={h.column.getToggleSortingHandler()} className="sortable">
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {h.column.getIsSorted() === "asc" && " ▴"}
                    {h.column.getIsSorted() === "desc" && " ▾"}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id}>
                {r.getVisibleCells().map((c) => (
                  <td key={c.id}>{formatCell(c.getValue())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3);
  return String(v);
}

function toCsv(columns: string[], rows: Record<string, any>[]): string {
  const escape = (v: unknown) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const out = [columns.join(",")];
  for (const r of rows) out.push(columns.map((c) => escape(r[c])).join(","));
  return out.join("\n");
}
