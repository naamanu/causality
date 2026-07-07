import type { LogLevel, Status } from "../api/types";

export const ms = (n: number) => `${n.toLocaleString()}ms`;
export const pct = (c: number) => `${Math.round(c * 100)}%`;

export const statusText: Record<Status, string> = {
  ok: "text-ok",
  degraded: "text-degraded",
  error: "text-error",
};

export const statusBg: Record<Status, string> = {
  ok: "bg-ok",
  degraded: "bg-degraded",
  error: "bg-error",
};

// Log level → text color (concrete grays, plus the status palette for warn/error).
export const levelText: Record<LogLevel, string> = {
  debug: "text-zinc-600",
  info: "text-zinc-400",
  warn: "text-degraded",
  error: "text-error",
};
