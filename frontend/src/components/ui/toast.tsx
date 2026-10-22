"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "@/lib/cn";

type ToastTone = "success" | "info" | "error";

interface ToastInput {
  tone?: ToastTone;
  title: string;
  message?: string;
}

interface ToastItem extends ToastInput {
  id: number;
}

interface ToastContextValue {
  push: (toast: ToastInput) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const icons = { success: CheckCircle2, info: Info, error: AlertTriangle };
const accents = {
  success: "text-forest-600",
  info: "text-lavender-700",
  error: "text-clay-600",
};

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: (id: number) => void }) {
  const tone = toast.tone ?? "info";
  const Icon = icons[tone];

  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), tone === "error" ? 9000 : 6000);
    return () => clearTimeout(timer);
  }, [toast.id, tone, onDismiss]);

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className="pointer-events-auto flex w-full gap-3 rounded-2xl border border-line bg-paper p-4 shadow-lift animate-rise"
    >
      <Icon className={cn("mt-0.5 size-5 shrink-0", accents[tone])} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-forest-900">{toast.title}</p>
        {toast.message ? <p className="mt-0.5 text-sm text-ink-700">{toast.message}</p> : null}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Fechar notificação"
        className="-m-2 grid size-11 shrink-0 place-items-center rounded-full text-ink-600 hover:bg-sand-100"
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const push = useCallback((toast: ToastInput) => {
    setItems((current) => [...current.slice(-3), { ...toast, id: Date.now() + Math.random() }]);
  }, []);

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] mx-auto flex max-w-md flex-col gap-3 p-4 pb-24 sm:pb-6 lg:left-auto lg:right-4 lg:mx-0">
        {items.map((item) => (
          <ToastCard key={item.id} toast={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast deve ser usado dentro de <ToastProvider>.");
  return context;
}
