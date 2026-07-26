/**
 * WebSocket client.
 *
 * Owns one socket for the whole app and hands frames to subscribers. The socket
 * is a delivery channel only — every write goes over HTTP — so a dropped
 * connection degrades the app to "not live" rather than "broken", and
 * reconnecting is always safe to retry.
 */

import { API_URL, getAccessToken } from "./api";

export type ServerEvent =
  | "message.new"
  | "message.updated"
  | "message.deleted"
  | "message.status"
  | "reaction.added"
  | "reaction.removed"
  | "conversation.updated"
  | "presence.update"
  | "error"
  | "pong";

export interface Frame<T = Record<string, unknown>> {
  type: ServerEvent | string;
  payload: T;
}

export type ConnectionState = "connecting" | "open" | "closed";

type FrameListener = (frame: Frame) => void;
type StateListener = (state: ConnectionState) => void;

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? API_URL.replace(/^http/, "ws");

/** Retry backoff in milliseconds, capped so a long outage still recovers promptly. */
const BACKOFF_MS = [500, 1000, 2000, 5000, 10000, 15000] as const;
const HEARTBEAT_MS = 25000;

class RealtimeClient {
  private socket: WebSocket | null = null;
  private frameListeners = new Set<FrameListener>();
  private stateListeners = new Set<StateListener>();
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private state: ConnectionState = "closed";
  /** Set when the caller asked to disconnect, so we do not fight them by reconnecting. */
  private intentionallyClosed = false;

  connect(): void {
    if (typeof window === "undefined") return; // no sockets during SSR
    const token = getAccessToken();
    if (!token) return;
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) return;

    this.intentionallyClosed = false;
    this.setState("connecting");

    const socket = new WebSocket(`${WS_URL}/ws?token=${encodeURIComponent(token)}`);
    this.socket = socket;

    socket.onopen = () => {
      this.attempt = 0; // a successful connection resets the backoff
      this.setState("open");
      this.startHeartbeat();
    };

    socket.onmessage = (event: MessageEvent<string>) => {
      let frame: Frame;
      try {
        frame = JSON.parse(event.data) as Frame;
      } catch {
        return; // a malformed frame is not worth tearing the connection down for
      }
      this.frameListeners.forEach((listener) => listener(frame));
    };

    socket.onclose = () => {
      this.stopHeartbeat();
      this.setState("closed");
      this.socket = null;
      if (!this.intentionallyClosed) this.scheduleReconnect();
    };

    socket.onerror = () => {
      // onclose always follows, so reconnection is handled in one place.
      socket.close();
    };
  }

  disconnect(): void {
    this.intentionallyClosed = true;
    this.clearReconnect();
    this.stopHeartbeat();
    this.socket?.close();
    this.socket = null;
    this.setState("closed");
  }

  send(type: string, payload: Record<string, unknown> = {}): void {
    // Dropped rather than queued: every client frame is an ephemeral signal
    // (typing, ping). Replaying a stale "typing" after a reconnect would show an
    // indicator for something the user finished saying long ago.
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    this.socket.send(JSON.stringify({ type, payload }));
  }

  onFrame(listener: FrameListener): () => void {
    this.frameListeners.add(listener);
    return () => this.frameListeners.delete(listener);
  }

  onStateChange(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    listener(this.state);
    return () => this.stateListeners.delete(listener);
  }

  get connectionState(): ConnectionState {
    return this.state;
  }

  private setState(state: ConnectionState): void {
    if (this.state === state) return;
    this.state = state;
    this.stateListeners.forEach((listener) => listener(state));
  }

  private scheduleReconnect(): void {
    this.clearReconnect();
    const delay = BACKOFF_MS[Math.min(this.attempt, BACKOFF_MS.length - 1)]!;
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private clearReconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  /**
   * Periodic ping.
   *
   * Proxies and load balancers close connections that look idle, and a socket
   * killed that way stays "open" on this side until a write fails. The ping both
   * keeps it alive and surfaces a dead connection quickly.
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => this.send("ping"), HEARTBEAT_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
  }
}

export const realtime = new RealtimeClient();
