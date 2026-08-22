import { apiUrl } from "../base";
export type ProviderInfo = {
  name: string;
  default_model: string;
  models: string[];
  available: boolean;
  error: string | null;
};

export type ProvidersResponse = {
  default_provider: string;
  default_effort: string;
  providers: ProviderInfo[];
};

export async function listProviders(): Promise<ProvidersResponse> {
  const res = await fetch(apiUrl("/api/providers"));
  if (!res.ok) throw new Error("listProviders failed");
  return res.json();
}
