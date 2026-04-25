import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createPin } from "../api/pins";
import type { ChartSpec } from "./ChartRenderer";

type Props = {
  query: string;
  chartSpec: ChartSpec | null;
};

export default function PinButton({ query, chartSpec }: Props) {
  const qc = useQueryClient();
  const mut = useMutation({
    mutationFn: () =>
      createPin({
        title: chartSpec?.title ?? "Vastgezette grafiek",
        query,
        chart_spec: chartSpec!,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pins"] }),
  });

  if (!chartSpec || !query) return null;

  return (
    <button
      className="pin-button"
      onClick={() => mut.mutate()}
      disabled={mut.isPending || mut.isSuccess}
      title="Vastzetten op Dashboard"
    >
      {mut.isSuccess ? "📌 Vastgezet" : mut.isPending ? "Bezig…" : "📌 Op dashboard zetten"}
    </button>
  );
}
