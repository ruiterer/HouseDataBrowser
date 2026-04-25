import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listProviders, type ProviderInfo } from "../api/providers";

export type Selection = { provider: string; model: string };

type Props = {
  value: Selection | null;
  onChange: (sel: Selection) => void;
  disabled?: boolean;
};

export default function ProviderPicker({ value, onChange, disabled }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["providers"],
    queryFn: listProviders,
    refetchInterval: 60_000,
  });

  const providers = data?.providers ?? [];
  const activeProvider = useMemo(
    () => providers.find((p) => p.name === value?.provider) ?? null,
    [providers, value],
  );

  // Initialise selection from server defaults the first time we load.
  useEffect(() => {
    if (!data || value) return;
    const first = providers.find((p) => p.available) ?? providers[0];
    if (!first) return;
    const stored = readStored();
    if (stored && providers.find((p) => p.name === stored.provider)?.available) {
      const provider = providers.find((p) => p.name === stored.provider)!;
      const model = provider.models.includes(stored.model) ? stored.model : provider.default_model;
      onChange({ provider: provider.name, model });
    } else {
      onChange({ provider: first.name, model: first.default_model });
    }
  }, [data, value, providers, onChange]);

  if (isLoading || !value || !activeProvider) {
    return <div className="provider-picker muted">providers laden…</div>;
  }

  function pickProvider(name: string) {
    const p = providers.find((x) => x.name === name);
    if (!p) return;
    const sel = { provider: p.name, model: p.default_model };
    writeStored(sel);
    onChange(sel);
  }

  function pickModel(model: string) {
    const sel = { provider: value!.provider, model };
    writeStored(sel);
    onChange(sel);
  }

  return (
    <div className="provider-picker">
      <label className="picker-label">
        <span>Provider</span>
        <select
          value={value.provider}
          onChange={(e) => pickProvider(e.target.value)}
          disabled={disabled}
        >
          {providers.map((p) => (
            <option key={p.name} value={p.name} disabled={!p.available}>
              {prettyProvider(p)}
            </option>
          ))}
        </select>
      </label>
      <label className="picker-label">
        <span>Model</span>
        <select
          value={value.model}
          onChange={(e) => pickModel(e.target.value)}
          disabled={disabled || activeProvider.models.length === 0}
        >
          {activeProvider.models.length === 0 && (
            <option value={value.model}>{value.model}</option>
          )}
          {activeProvider.models.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </label>
      {!activeProvider.available && (
        <span className="picker-error">
          {activeProvider.name} niet bereikbaar{activeProvider.error ? `: ${activeProvider.error}` : ""}
        </span>
      )}
    </div>
  );
}

function prettyProvider(p: ProviderInfo): string {
  if (p.name === "claude") return "Claude (cloud)";
  if (p.name === "ollama") return p.available ? "Ollama (lokaal)" : "Ollama — offline";
  return p.name;
}

const STORAGE_KEY = "housedatabrowser.llm";

function readStored(): Selection | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v ? JSON.parse(v) : null;
  } catch {
    return null;
  }
}

function writeStored(sel: Selection): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sel));
  } catch {
    /* ignore quota errors */
  }
}
