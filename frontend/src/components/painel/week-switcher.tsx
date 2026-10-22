"use client";

import { ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { addWeeks, formatWeekRange, startOfWeek, toISODate } from "@/lib/dates";
import { useNow } from "@/lib/hooks/use-now";

/** Retorna a semana atual (após hidratação) e a semana escolhida. */
export function useWeekSelection(selected: string | null) {
  const now = useNow();
  const current = now ? toISODate(startOfWeek(now)) : null;
  return { current, week: selected ?? current };
}

interface WeekSwitcherProps {
  week: string | null;
  current: string | null;
  onChange: (week: string) => void;
}

export function WeekSwitcher({ week, current, onChange }: WeekSwitcherProps) {
  const isCurrent = week !== null && week === current;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2" role="group" aria-label="Navegar entre semanas">
        <Button
          variant="secondary"
          size="sm"
          className="size-11 px-0!"
          aria-label="Semana anterior"
          disabled={!week}
          onClick={() => week && onChange(addWeeks(week, -1))}
        >
          <ChevronLeft className="size-5" aria-hidden />
        </Button>
        <div className="min-w-48 px-2 text-center">
          <p className="eyebrow">{isCurrent ? "Esta semana" : "Semana"}</p>
          <p className="mt-1.5 font-display text-xl text-forest-900" aria-live="polite">
            {week ? formatWeekRange(week) : "Carregando…"}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="size-11 px-0!"
          aria-label="Próxima semana"
          disabled={!week}
          onClick={() => week && onChange(addWeeks(week, 1))}
        >
          <ChevronRight className="size-5" aria-hidden />
        </Button>
      </div>
      {!isCurrent && current ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange(current)}
          icon={<RotateCcw className="size-4" aria-hidden />}
        >
          Esta semana
        </Button>
      ) : null}
    </div>
  );
}
