// The REST client — the missing api.ts (Doc 03 §9, Doc 04 §6).
//
// Commands go to the Python engine over REST and return 202 ("accepted"); the *result* is
// never in the HTTP response — it arrives on the event stream (see streamClient.ts). So
// these calls return the small acknowledgement bodies only. Truth comes back on the stream.
//
// No secrets here. The engine base URL is a VITE_ var; the browser holds a session id only.

const ENGINE_URL: string =
  import.meta.env.VITE_ENGINE_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${ENGINE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${init?.method ?? "GET"} ${path} → ${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  req<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

// --- request/response shapes (mirror the engine's Pydantic bodies) ---------------------

export interface CreateHuntBody {
  input?: string;
  instinct_id?: string;
  source?: "typed" | "spoken" | "dropped";
}
export interface HuntCreated {
  hunt_id: string;
  state: string;
}
export interface HuntSnapshot {
  hunt_id: string;
  state: string;
  last_seq: number;
  task: string;
}
export interface ApprovePlanBody {
  mode: "wild" | "on_signal" | "on_command";
  boundary_usd: number;
  edits?: Record<string, unknown>;
}
export interface ResolveHoldBody {
  resolution: string;
  edited_text?: string | null;
}
export interface CommandAccepted {
  hunt_id: string;
  accepted: boolean;
}
export interface Instinct {
  instinct_id: string;
  label: string;
  spec: Record<string, unknown>;
}
export interface HuntListItem {
  hunt_id: string;
  state: string;
  source: string;
  title: string;
  boundary_usd: number | null;
  created_at: string;
}
export interface FinalArtifact {
  artifact_id: string;
  hunt_id: string;
  kind: string;
  produced_by: string | null;
  content: Record<string, unknown> | null;
}

// --- the surface -----------------------------------------------------------------------

export const api = {
  createHunt: (body: CreateHuntBody) => post<HuntCreated>("/hunts", body),
  listHunts: () => req<{ hunts: HuntListItem[] }>("/hunts"),
  getHunt: (id: string) => req<HuntSnapshot>(`/hunts/${id}`),
  getArtifact: (id: string) => req<FinalArtifact>(`/hunts/${id}/artifact`),
  approvePlan: (id: string, body: ApprovePlanBody) =>
    post<CommandAccepted>(`/hunts/${id}/plan/approve`, body),
  resolveHold: (id: string, holdId: string, body: ResolveHoldBody) =>
    post<CommandAccepted>(`/hunts/${id}/holds/${holdId}/resolve`, body),
  ask: (id: string, question: string) =>
    post<{ reply: string }>(`/hunts/${id}/ask`, { question }),
  addInput: (id: string) => post<CommandAccepted>(`/hunts/${id}/inputs`),
  stop: (id: string) => post<CommandAccepted>(`/hunts/${id}/stop`),
  resume: (id: string, boundary_usd: number) =>
    post<CommandAccepted>(`/hunts/${id}/resume`, { boundary_usd }),
  benchmark: (id: string) => post<CommandAccepted>(`/hunts/${id}/benchmark`),
  listInstincts: () => req<{ instincts: Instinct[] }>("/instincts"),
  saveInstinct: (label: string, spec: Record<string, unknown>) =>
    post<{ instinct_id: string; accepted: boolean }>("/instincts", { label, spec }),
  exportTracks: (id: string) =>
    req<{ hunt_id: string; events: unknown[]; redacted: boolean }>(
      `/hunts/${id}/tracks/export`,
    ),
  signedUpload: () => post<{ upload_url: string; object_key: string }>("/uploads"),
};
