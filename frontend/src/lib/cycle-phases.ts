import type { CyclePhase } from "@/lib/types";

/** Fases do ciclo semanal na ordem em que acontecem. */
export const cyclePhases: { id: CyclePhase; label: string }[] = [
  { id: "collecting_availability", label: "Disponibilidades" },
  { id: "enrollment_pending", label: "Agenda preparada, aguardando abertura das inscrições" },
  { id: "enrollment_open", label: "Inscrições abertas" },
  { id: "in_progress", label: "Semana em andamento" },
  { id: "closed", label: "Encerrada" },
];

/** Rótulo legível de uma fase; `null` quando o ciclo ainda não existe. */
export function cyclePhaseLabel(phase: CyclePhase | null | undefined): string | null {
  return cyclePhases.find((item) => item.id === phase)?.label ?? null;
}

export function cyclePhaseIndex(phase: CyclePhase): number {
  return cyclePhases.findIndex((item) => item.id === phase);
}
