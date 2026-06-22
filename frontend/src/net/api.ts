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

const patch = <T>(path: string, body?: unknown) =>
  req<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined });

const del = <T>(path: string) => req<T>(path, { method: "DELETE" });

// Multipart (file upload) — let the browser set the boundary; never set Content-Type here.
async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${ENGINE_URL}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`POST ${path} → ${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

// --- request/response shapes (mirror the engine's Pydantic bodies) ---------------------

export type StrategyName = "orchestrate" | "deep_dive" | "critique";

export interface CreateHuntBody {
  input?: string;
  instinct_id?: string;
  source?: "typed" | "spoken" | "dropped";
  strategy?: StrategyName;
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
  strategy?: StrategyName;
}
export interface StrategyInfo {
  name: StrategyName;
  label: string;
  pattern: string;
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
export interface IntakeTurn {
  role: "user" | "assistant";
  content: string;
}
export interface IntakeReply {
  reply: string;
  ready: boolean;
  brief: string;
}
export interface ParsedDoc {
  kind: string;
  text: string;
  chars: number;
  filename?: string;
}
export interface TranscriptReply {
  text: string;
  provider: string;
  duration_s: number;
}
export interface ScorecardRun {
  quality: number;
  citations: number;
  cost_usd: number;
  time_s: number;
  sources: number;
}
export interface Scorecard {
  lone_wolf: ScorecardRun;
  pack: ScorecardRun;
}

// --- the surface -----------------------------------------------------------------------

export const api = {
  intake: (messages: IntakeTurn[]) => post<IntakeReply>("/hunts/intake", { messages }),
  createHunt: (body: CreateHuntBody) => post<HuntCreated>("/hunts", body),
  getStrategies: () =>
    req<{ strategies: StrategyInfo[]; default: StrategyName }>("/strategies"),
  listHunts: () => req<{ hunts: HuntListItem[] }>("/hunts"),
  getHunt: (id: string) => req<HuntSnapshot>(`/hunts/${id}`),
  patchHunt: (id: string, body: { title?: string; archived?: boolean }) =>
    patch<{ hunt_id: string; ok: boolean }>(`/hunts/${id}`, body),
  deleteHunt: (id: string) => del<{ hunt_id: string; deleted: boolean }>(`/hunts/${id}`),
  getMessages: (id: string) =>
    req<{ messages: { role: "user" | "alpha"; text: string }[] }>(`/hunts/${id}/messages`),
  saveMessage: (id: string, role: "user" | "alpha", content: string) =>
    post<{ ok: boolean }>(`/hunts/${id}/messages`, { role, content }),
  getArtifact: (id: string) => req<FinalArtifact>(`/hunts/${id}/artifact`),
  approvePlan: (id: string, body: ApprovePlanBody) =>
    post<CommandAccepted>(`/hunts/${id}/plan/approve`, body),
  resolveHold: (id: string, holdId: string, body: ResolveHoldBody) =>
    post<CommandAccepted>(`/hunts/${id}/holds/${holdId}/resolve`, body),
  // Multi-turn: pass the conversation so far so Alpha remembers the thread.
  ask: (id: string, messages: IntakeTurn[]) =>
    post<{ reply: string }>(`/hunts/${id}/ask`, { messages }),
  addInput: (id: string, text: string, kind = "text") =>
    post<CommandAccepted>(`/hunts/${id}/inputs`, { text, kind }),
  stop: (id: string) => post<CommandAccepted>(`/hunts/${id}/stop`),
  resume: (id: string, boundary_usd: number) =>
    post<CommandAccepted>(`/hunts/${id}/resume`, { boundary_usd }),
  benchmark: (id: string) => post<CommandAccepted>(`/hunts/${id}/benchmark`),
  getScorecard: (id: string) =>
    req<{ hunt_id: string; scorecard: Scorecard }>(`/hunts/${id}/scorecard`),
  // Parse a dropped file (or URL) into text the pack can research.
  parse: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return postForm<ParsedDoc>("/parse", form);
  },
  // Transcribe an uploaded audio file into text (for a new hunt from voice).
  transcribe: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return postForm<TranscriptReply>("/transcribe", form);
  },
  listInstincts: () => req<{ instincts: Instinct[] }>("/instincts"),
  saveInstinct: (label: string, spec: Record<string, unknown>) =>
    post<{ instinct_id: string; accepted: boolean }>("/instincts", { label, spec }),
  exportTracks: (id: string) =>
    req<{ hunt_id: string; events: unknown[]; redacted: boolean }>(
      `/hunts/${id}/tracks/export`,
    ),
  signedUpload: () => post<{ upload_url: string; object_key: string }>("/uploads"),
};
