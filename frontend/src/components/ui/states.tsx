import type { ComponentType, ReactNode } from "react";
import { CloudOff, RefreshCw, ServerCrash, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { ApiError } from "@/lib/api/errors";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("animate-pulse rounded-xl bg-sand-100 motion-reduce:animate-none", className)}
    />
  );
}

/** Esqueleto de lista de cartões, anunciado como "carregando" para leitores de tela. */
export function LoadingBlock({ rows = 3, label = "Carregando…" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-4">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="rounded-(--radius-card) border border-line bg-paper p-5 shadow-soft">
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="mt-4 h-7 w-2/3" />
          <Skeleton className="mt-4 h-4 w-1/2" />
        </div>
      ))}
    </div>
  );
}

interface EmptyStateProps {
  icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-(--radius-card) border border-dashed border-line-strong bg-sand-50/60 px-6 py-12 text-center",
        className,
      )}
    >
      <span className="grid size-14 place-items-center rounded-full bg-sage-100 text-forest-700">
        <Icon className="size-6" aria-hidden />
      </span>
      <h3 className="mt-5 font-display text-xl text-forest-900">{title}</h3>
      {description ? <div className="mt-2 max-w-md text-ink-600">{description}</div> : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

const errorTitles: Record<ApiError["kind"], { title: string; icon: EmptyStateProps["icon"] }> = {
  not_configured: { title: "Servidor ainda não configurado", icon: CloudOff },
  network: { title: "Sem conexão com o servidor", icon: CloudOff },
  timeout: { title: "O servidor demorou a responder", icon: CloudOff },
  unauthenticated: { title: "Entre para continuar", icon: ShieldAlert },
  forbidden: { title: "Acesso não autorizado", icon: ShieldAlert },
  not_found: { title: "Não encontrado", icon: ServerCrash },
  conflict: { title: "A situação mudou", icon: ServerCrash },
  validation: { title: "Dados não aceitos", icon: ServerCrash },
  server: { title: "Algo deu errado no servidor", icon: ServerCrash },
  unknown: { title: "Algo inesperado aconteceu", icon: ServerCrash },
};

interface ErrorStateProps {
  error: ApiError;
  onRetry?: () => void;
  action?: ReactNode;
  className?: string;
}

export function ErrorState({ error, onRetry, action, className }: ErrorStateProps) {
  const meta = errorTitles[error.kind];
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center rounded-(--radius-card) border border-clay-200 bg-clay-50/70 px-6 py-12 text-center",
        className,
      )}
    >
      <span className="grid size-14 place-items-center rounded-full bg-clay-100 text-clay-600">
        <meta.icon className="size-6" aria-hidden />
      </span>
      <h3 className="mt-5 font-display text-xl text-forest-900">{meta.title}</h3>
      <p className="mt-2 max-w-md text-ink-700">{error.message}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {onRetry && error.kind !== "not_configured" ? (
          <Button variant="secondary" onClick={onRetry} icon={<RefreshCw className="size-4" aria-hidden />}>
            Tentar novamente
          </Button>
        ) : null}
        {action}
      </div>
    </div>
  );
}
