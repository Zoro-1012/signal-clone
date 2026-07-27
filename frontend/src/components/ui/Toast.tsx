"use client";

import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type ToastKind = "success" | "error" | "info";

interface Toast {
  id: string;
  kind: ToastKind;
  message: string;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

/** Auto-dismiss delay. Errors linger, because they usually need reading twice. */
const DURATION: Record<ToastKind, number> = { success: 3000, info: 4000, error: 6000 };

const ICONS: Record<ToastKind, typeof Info> = {
  success: CheckCircle2,
  error: TriangleAlert,
  info: Info,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = crypto.randomUUID();
      setToasts((current) => [...current, { id, kind, message }]);
      setTimeout(() => dismiss(id), DURATION[kind]);
    },
    [dismiss],
  );

  // Memoised so consumers do not re-render on every toast state change.
  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => push("success", message),
      error: (message) => push("error", message),
      info: (message) => push("info", message),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      {/* aria-live=polite announces new toasts without interrupting; assertive
          would talk over whatever the user is reading. role=status pairs with it
          so the region is recognised even before the first toast exists. */}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 left-1/2 z-toast flex w-[min(24rem,calc(100vw-2rem))] -translate-x-1/2 flex-col gap-2"
      >
        {toasts.map((toast) => {
          const Icon = ICONS[toast.kind];
          return (
            <div
              key={toast.id}
              className={cn(
                "pointer-events-auto flex items-center gap-3 rounded-xl px-4 py-3 shadow-lg animate-slide-up",
                "border border-edge-subtle bg-surface-raised",
                toast.kind === "error" && "border-signal-red/40",
              )}
            >
              <Icon
                className={cn(
                  "h-5 w-5 shrink-0",
                  toast.kind === "success" && "text-signal-green",
                  toast.kind === "error" && "text-signal-red",
                  toast.kind === "info" && "text-accent",
                )}
                aria-hidden="true"
              />
              <p className="min-w-0 flex-1 text-sm text-content-primary">{toast.message}</p>
              <button
                onClick={() => dismiss(toast.id)}
                aria-label="Dismiss"
                className="shrink-0 rounded-full p-1 text-content-tertiary hover:bg-surface-hover"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast must be used inside <ToastProvider>");
  return api;
}
