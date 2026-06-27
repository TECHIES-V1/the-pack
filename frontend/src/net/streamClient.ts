// The live stream client — WebSocket to the Rust gateway (Doc 03 §9, Doc 04 §2).
//
//   gateway WS /hunts/:id/stream?from_seq=n  ->  PackEvent per text frame  ->  store.apply
//
// The gateway replays from `from_seq` then live-tails, sending each event as one JSON text
// frame (the envelope directly). On disconnect we reconnect and resume from lastSeq+1, so
// the gateway replays exactly the gap — no missed or double-applied events (the reducer also
// drops seq <= lastSeq, so a re-sent event is a harmless no-op).

import type { PackEvent } from "@/events/types";

// Resolve the gateway WS base. An absolute value (ws://… / wss://…) is used as-is; a relative
// one (e.g. "/ws", the prod default behind nginx) is resolved against the page origin, so the
// same build works on any host/domain and picks wss automatically under HTTPS.
function wsBase(): string {
  const configured = import.meta.env.VITE_GATEWAY_WS_URL ?? "ws://localhost:8080";
  if (/^wss?:\/\//i.test(configured)) return configured;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const path = configured.startsWith("/") ? configured : `/${configured}`;
  return `${proto}//${window.location.host}${path}`;
}

export interface StreamHandlers {
  onEvent: (ev: PackEvent) => void;
  getResumeSeq: () => number; // lastSeq applied so far; -1 before anything
  onStatus?: (status: "connecting" | "open" | "closed") => void;
}

export class StreamClient {
  private ws: WebSocket | null = null;
  private closedByUs = false;
  private retry = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly huntId: string,
    private readonly handlers: StreamHandlers,
  ) {}

  connect(): void {
    this.closedByUs = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer); // don't orphan a pending reconnect
    this.reconnectTimer = null;
    this.open();
  }

  close(): void {
    this.closedByUs = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  private open(): void {
    const fromSeq = this.handlers.getResumeSeq() + 1; // resume just past what we have
    const url = `${wsBase()}/hunts/${this.huntId}/stream?from_seq=${fromSeq}`;
    this.handlers.onStatus?.("connecting");

    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.retry = 0;
      this.handlers.onStatus?.("open");
    };

    ws.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data as string) as PackEvent;
        this.handlers.onEvent(ev);
      } catch {
        // A non-JSON frame is not ours — ignore it rather than crash the stream.
      }
    };

    ws.onclose = () => {
      this.handlers.onStatus?.("closed");
      if (!this.closedByUs) this.scheduleReconnect();
    };

    ws.onerror = () => ws.close();
  }

  private scheduleReconnect(): void {
    // Exponential backoff, capped — resume picks up the gap from from_seq.
    const delay = Math.min(1000 * 2 ** this.retry, 10_000);
    this.retry += 1;
    this.reconnectTimer = setTimeout(() => this.open(), delay);
  }
}
