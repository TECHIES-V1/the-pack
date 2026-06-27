// The REST client — the missing api.ts (Doc 03 §9, Doc 04 §6).
//
// Commands go to the Python engine over REST and return 202 ("accepted"); the *result* is
// never in the HTTP response — it arrives on the event stream (see streamClient.ts). So
// these calls return the small acknowledgement bodies only. Truth comes back on the stream.
//
// No secrets here. The engine base URL is a VITE_ var; the browser holds a session id only.

const ENGINE_URL: string =
  import.meta.env.VITE_ENGINE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
  }
  get kind(): "engine_down" | "rate_limit" | "timeout" | "content_filter" | "context_exceeded" | "unknown" {
    if (this.status === 429) return "rate_limit";
    if (this.status === 503 || this.status === 0) return "engine_down";
    if (this.detail.includes("timeout")) return "timeout";
    if (this.detail.includes("content_filter")) return "content_filter";
    if (this.detail.includes("context_length") || this.detail.includes("context_exceeded")) return "context_exceeded";
    return "unknown";
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${ENGINE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function* streamSSE(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<Record<string, unknown>> {
  let res: Response;
  try {
    res = await fetch(`${ENGINE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    throw new ApiError(0, "engine_down");
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(res.status, detail);
  }
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try { yield JSON.parse(line.slice(6)); } catch { /* skip malformed */ }
        }
      }
    }
  } finally {
    reader.cancel();
  }
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
export interface RehearseResult {
  est_cost_usd: number;
  est_time_s: number;
  calls: number;
  scouts: number;
  warnings: string[];
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
  project_id: string | null;
  created_at: string;
}
export interface Project {
  project_id: string;
  label: string;
  instructions: string | null;
  hunt_count: number;
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
  listHunts: (projectId?: string) =>
    req<{ hunts: HuntListItem[] }>(`/hunts${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`),
  getHunt: (id: string) => req<HuntSnapshot>(`/hunts/${id}`),
  patchHunt: (id: string, body: { title?: string; archived?: boolean; project_id?: string | null }) =>
    patch<{ hunt_id: string; ok: boolean }>(`/hunts/${id}`, body),
  deleteHunt: (id: string) => del<{ hunt_id: string; deleted: boolean }>(`/hunts/${id}`),
  // Projects (workspaces that group hunts)
  listProjects: () => req<{ projects: Project[] }>("/projects"),
  createProject: (label: string, instructions?: string) =>
    post<{ project_id: string; label: string }>("/projects", { label, instructions }),
  patchProject: (id: string, body: { label?: string; instructions?: string }) =>
    patch<{ project_id: string; ok: boolean }>(`/projects/${id}`, body),
  deleteProject: (id: string) => del<{ project_id: string; deleted: boolean }>(`/projects/${id}`),
  getMessages: (id: string) =>
    req<{ messages: { role: "user" | "alpha"; text: string }[] }>(`/hunts/${id}/messages`),
  saveMessage: (id: string, role: "user" | "alpha", content: string) =>
    post<{ ok: boolean }>(`/hunts/${id}/messages`, { role, content }),
  shareHunt: (id: string) => post<{ token: string }>(`/hunts/${id}/share`),
  getShared: (token: string) =>
    req<{ title: string; content: Record<string, unknown> | null }>(`/share/${token}`),
  getArtifact: (id: string) => req<FinalArtifact>(`/hunts/${id}/artifact`),
  approvePlan: (id: string, body: ApprovePlanBody) =>
    post<CommandAccepted>(`/hunts/${id}/plan/approve`, body),
  // Shadow Hunt: estimate a team's cost/time before launching (v2). No spend, no events.
  rehearse: (id: string, team: unknown[], strategy?: string) =>
    post<RehearseResult>(`/hunts/${id}/rehearse`, { team, strategy }),
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
  submitFeedback: (huntId: string, turnIndex: number, vote: "up" | "down") =>
    post<{ ok: boolean }>(`/hunts/${huntId}/feedback`, { turn_index: turnIndex, vote }),
};
