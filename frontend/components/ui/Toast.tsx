"use client";

import { cn } from "@/lib/utils";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export type ToastTone = "default" | "success" | "error" | "warning";

export type ToastMessage = {
  id: string;
  title: string;
  description?: string;
  tone?: ToastTone;
};

type ToastContextValue = {
  toasts: ToastMessage[];
  push: (toast: Omit<ToastMessage, "id">) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
  dismiss: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const TONE_SHELL: Record<ToastTone, string> = {
  default: "border-[var(--tb-line)] bg-[var(--tb-surface)] text-[var(--tb-ink)]",
  success:
    "border-[color-mix(in_srgb,var(--tb-success)_28%,transparent)] bg-[var(--tb-surface)] text-[var(--tb-ink)]",
  error:
    "border-[color-mix(in_srgb,var(--tb-danger)_28%,transparent)] bg-[var(--tb-surface)] text-[var(--tb-ink)]",
  warning:
    "border-[color-mix(in_srgb,var(--tb-warning)_28%,transparent)] bg-[var(--tb-surface)] text-[var(--tb-ink)]",
};

const TONE_DOT: Record<ToastTone, string> = {
  default: "bg-[var(--tb-ink)]",
  success: "bg-[var(--tb-success)]",
  error: "bg-[var(--tb-danger)]",
  warning: "bg-[var(--tb-warning)]",
};

function ToastViewport({
  toasts,
  dismiss,
}: {
  toasts: ToastMessage[];
  dismiss: (id: string) => void;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return createPortal(
    <div
      aria-live="polite"
      className="pointer-events-none fixed top-4 right-4 z-[200] flex w-[min(100%-2rem,20rem)] flex-col items-end gap-2"
    >
      {toasts.map((toast) => {
        const tone = toast.tone ?? "default";
        return (
          <div
            key={toast.id}
            role="status"
            className={cn(
              "pointer-events-auto flex w-full items-start gap-2.5 overflow-hidden rounded-xl border px-3 py-2.5 shadow-[0_10px_28px_-12px_rgba(13,59,42,0.35)] animate-[tb-toast-in_180ms_ease-out]",
              TONE_SHELL[tone],
            )}
          >
            <span
              aria-hidden
              className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", TONE_DOT[tone])}
            />
            <div className="min-w-0 flex-1 pt-px">
              <p className="truncate text-[13px] font-semibold leading-snug tracking-tight">
                {toast.title}
              </p>
              {toast.description ? (
                <p className="mt-0.5 truncate text-[12px] leading-snug text-[var(--tb-muted-fg)]">
                  {toast.description}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              aria-label="Dismiss"
              className="-mr-0.5 -mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[15px] leading-none text-[var(--tb-muted-fg)] transition hover:bg-[var(--tb-hover)] hover:text-[var(--tb-ink)]"
              onClick={() => dismiss(toast.id)}
            >
              ×
            </button>
          </div>
        );
      })}
    </div>,
    document.body,
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (toast: Omit<ToastMessage, "id">) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev.slice(-3), { ...toast, id }]);
      window.setTimeout(() => dismiss(id), 2800);
    },
    [dismiss],
  );

  const success = useCallback(
    (title: string, description?: string) => push({ title, description, tone: "success" }),
    [push],
  );
  const error = useCallback(
    (title: string, description?: string) => push({ title, description, tone: "error" }),
    [push],
  );
  const warning = useCallback(
    (title: string, description?: string) => push({ title, description, tone: "warning" }),
    [push],
  );

  const value = useMemo(
    () => ({ toasts, push, success, error, warning, dismiss }),
    [toasts, push, success, error, warning, dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} dismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
