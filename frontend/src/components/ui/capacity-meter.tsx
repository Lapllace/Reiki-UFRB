import { cn } from "@/lib/cn";

interface CapacityMeterProps {
  capacity: number | null;
  confirmed: number | null;
  waitlist?: number | null;
  className?: string;
}

/** Barra de ocupação. Se o backend não informar capacidade, não inventa números. */
export function CapacityMeter({ capacity, confirmed, waitlist, className }: CapacityMeterProps) {
  if (capacity === null || confirmed === null) {
    return (
      <p className={cn("text-sm text-ink-600", className)}>Vagas não informadas para esta sessão.</p>
    );
  }
  const ratio = capacity > 0 ? Math.min(1, confirmed / capacity) : 1;
  const free = Math.max(0, capacity - confirmed);
  const full = free === 0;
  const tight = !full && ratio >= 0.7;

  return (
    <div className={className}>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className={cn("font-semibold", full ? "text-honey-700" : "text-forest-800")}>
          {full ? "Sem vagas" : free === 1 ? "1 vaga disponível" : `${free} vagas disponíveis`}
        </span>
        <span className="text-ink-600">
          {confirmed}/{capacity}
        </span>
      </div>
      <div
        role="meter"
        aria-label="Ocupação da sessão"
        aria-valuemin={0}
        aria-valuemax={capacity}
        aria-valuenow={Math.min(confirmed, capacity)}
        aria-valuetext={`${confirmed} de ${capacity} vagas ocupadas`}
        className="mt-2 h-2 overflow-hidden rounded-full bg-sand-200"
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500",
            full ? "bg-honey-600" : tight ? "bg-sage-600" : "bg-sage-400",
          )}
          style={{ width: `${Math.max(ratio * 100, confirmed > 0 ? 6 : 0)}%` }}
        />
      </div>
      {full && waitlist ? (
        <p className="mt-2 text-sm text-ink-600">
          {waitlist === 1 ? "1 pessoa na fila de espera" : `${waitlist} pessoas na fila de espera`}
        </p>
      ) : null}
    </div>
  );
}
