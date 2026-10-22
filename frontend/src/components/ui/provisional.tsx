import type { ReactNode } from "react";
import { FileClock, Hourglass } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

/** Selo para textos gerais ainda não revisados/confirmados pela coordenação. */
export function ProvisionalBadge({ className }: { className?: string }) {
  return (
    <Badge tone="honey" icon={FileClock} className={className}>
      Texto provisório
    </Badge>
  );
}

/** Substitui um dado institucional que ainda não foi informado. Nunca inventamos o valor. */
export function PendingValue({ children = "A confirmar pela coordenação" }: { children?: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md bg-honey-50 px-2 py-0.5 text-[0.9em] font-medium text-honey-700 ring-1 ring-inset ring-honey-200">
      <Hourglass className="size-3.5" aria-hidden />
      {children}
    </span>
  );
}

/** Caixa que separa conteúdo provisório do que será confirmado institucionalmente. */
export function ProvisionalNote({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <aside
      className={cn(
        "flex gap-3 rounded-2xl border border-honey-200 bg-honey-50/80 p-4 text-sm leading-relaxed text-honey-700",
        className,
      )}
    >
      <FileClock className="mt-0.5 size-5 shrink-0" aria-hidden />
      <div>{children}</div>
    </aside>
  );
}
