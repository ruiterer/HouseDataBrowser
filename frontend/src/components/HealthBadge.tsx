import { useQuery } from "@tanstack/react-query";

type Health = {
  status: string;
  influx: { connected: boolean; version?: string; error?: string; database?: string };
  llm: { provider: string; model: string };
};

async function fetchHealth(): Promise<Health> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("health check failed");
  return res.json();
}

export default function HealthBadge() {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });

  if (isError || !data) {
    return <span className="health-badge bad">backend offline</span>;
  }

  const ok = data.influx.connected;
  return (
    <span className={`health-badge ${ok ? "good" : "bad"}`} title={JSON.stringify(data, null, 2)}>
      {ok ? `influx ✓ · ${data.llm.provider}` : "influx ✗"}
    </span>
  );
}
