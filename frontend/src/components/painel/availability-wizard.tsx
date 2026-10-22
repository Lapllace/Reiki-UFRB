"use client";

import { useMemo, useState } from "react";
import {
  CalendarCheck2,
  CalendarX2,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  MapPin,
  Send,
} from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/section";
import { ErrorState, LoadingBlock } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { toApiError } from "@/lib/api/errors";
import { cn } from "@/lib/cn";
import {
  addWeeks,
  formatDateTime,
  formatDayLong,
  formatTime,
  formatTimeRange,
  formatWeekRange,
  localDateKey,
} from "@/lib/dates";
import { plural } from "@/lib/format";
import { useAccountResource } from "@/lib/hooks/use-account-resource";
import type { SlotOption, WeeklyAvailability } from "@/lib/types";

type Mode = "available" | "unavailable";
interface Draft {
  key: string;
  mode: Mode;
  selected: string[];
}

const steps = ["Situação", "Horários", "Resumo"] as const;

function groupByDay(options: SlotOption[]) {
  const map = new Map<string, SlotOption[]>();
  for (const option of [...options].sort((a, b) => a.startsAt.localeCompare(b.startsAt))) {
    const key = localDateKey(option.startsAt);
    map.set(key, [...(map.get(key) ?? []), option]);
  }
  return [...map.entries()];
}

const statusLabel: Record<WeeklyAvailability["status"], { text: string; tone: "sage" | "forest" | "honey" }> = {
  pending: { text: "Ainda não registrada", tone: "honey" },
  published: { text: "Disponibilidade publicada", tone: "forest" },
  submitted: { text: "Disponibilidade registrada", tone: "forest" },
  unavailable: { text: "Indisponibilidade declarada", tone: "sage" },
};

export function AvailabilityWizard() {
  const toast = useToast();
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);
  const [confirmedWeek, setConfirmedWeek] = useState<string | null>(null);

  const { data, error, loading, refreshing, reload } = useAccountResource(
    `availability:${weekStart ?? "open"}`,
    (signal) => api.availability.get(weekStart, signal),
  );

  const current: Draft | null = useMemo(() => {
    if (!data) return null;
    if (draft?.key === data.weekStart) return draft;
    return {
      key: data.weekStart,
      mode: data.status === "unavailable" ? "unavailable" : "available",
      selected: data.selectedSlotIds ?? [],
    };
  }, [data, draft]);

  const days = useMemo(() => (data ? groupByDay(data.options ?? []) : []), [data]);
  const optionById = useMemo(() => new Map((data?.options ?? []).map((option) => [option.id, option])), [data]);

  function navigate(delta: number) {
    if (!data) return;
    setWeekStart(addWeeks(data.weekStart, delta));
    setStep(0);
    setDraft(null);
    setStepError(null);
    setPublishError(null);
    setConfirmedWeek(null);
  }

  function update(partial: Partial<Draft>) {
    if (!data || !current) return;
    setDraft({ ...current, ...partial });
    setStepError(null);
  }

  function toggle(id: string) {
    if (!current) return;
    const selected = current.selected.includes(id)
      ? current.selected.filter((item) => item !== id)
      : [...current.selected, id];
    update({ selected });
  }

  function next() {
    if (!current) return;
    if (step === 0) {
      setStep(current.mode === "unavailable" ? 2 : 1);
      return;
    }
    if (step === 1 && current.selected.length === 0) {
      setStepError("Selecione ao menos um horário ou volte e declare indisponibilidade.");
      return;
    }
    setStep((value) => value + 1);
  }

  function back() {
    if (!current) return;
    setStep((value) => (value === 2 && current.mode === "unavailable" ? 0 : value - 1));
  }

  async function publish() {
    if (!data || !current) return;
    setPublishing(true);
    setPublishError(null);
    try {
      const saved = await api.availability.publish({
        weekStart: data.weekStart,
        unavailable: current.mode === "unavailable",
        entries: current.mode === "unavailable"
          ? []
          : current.selected
              .map((id) => optionById.get(id))
              .filter((option): option is SlotOption => Boolean(option))
              .map((option) => ({
                startsAt: option.startsAt,
                endsAt: option.endsAt,
                locationId: option.location.id,
              })),
        slotIds: current.mode === "unavailable" ? [] : current.selected,
      });
      setDraft(null);
      setStep(0);
      setConfirmedWeek(saved.weekStart);
      toast.push({
        tone: "success",
        title: saved.status === "unavailable" ? "Indisponibilidade registrada" : "Disponibilidade publicada",
        message: "O sistema confirmou o seu registro.",
      });
      reload();
    } catch (caught) {
      setPublishError(toApiError(caught).message);
    } finally {
      setPublishing(false);
    }
  }

  const readOnlySelected = (data?.selectedSlotIds ?? [])
    .map((id) => optionById.get(id))
    .filter((option): option is SlotOption => Boolean(option));

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Ministrante"
        title="Disponibilidade semanal"
        description="Registre os horários em que você pode conduzir sessões ou declare que estará indisponível na semana."
      />

      {/* Seletor de semana */}
      <div className="flex items-center gap-2" role="group" aria-label="Navegar entre semanas">
        <Button
          variant="secondary"
          size="sm"
          className="size-11 px-0!"
          aria-label="Semana anterior"
          disabled={!data}
          onClick={() => navigate(-1)}
        >
          <ChevronLeft className="size-5" aria-hidden />
        </Button>
        <div className="min-w-0 flex-1 px-2 text-center sm:max-w-sm sm:flex-none">
          <p className="eyebrow">Semana</p>
          <p className="mt-1.5 font-display text-xl text-forest-900 sm:text-2xl" aria-live="polite">
            {data ? formatWeekRange(data.weekStart) : "Carregando…"}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="size-11 px-0!"
          aria-label="Próxima semana"
          disabled={!data}
          onClick={() => navigate(1)}
        >
          <ChevronRight className="size-5" aria-hidden />
        </Button>
        {refreshing ? <span className="ml-2 text-sm text-ink-600">Atualizando…</span> : null}
      </div>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading || !data || !current ? (
        <LoadingBlock rows={2} label="Carregando disponibilidade…" />
      ) : (
        <>
          {confirmedWeek === data.weekStart ? (
            <Alert tone="success" title="Registro confirmado pelo sistema" onDismiss={() => setConfirmedWeek(null)}>
              Sua situação nesta semana foi atualizada. Você ainda pode editá-la enquanto o registro estiver aberto.
            </Alert>
          ) : null}

          <Card className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-2">
              <Badge tone={statusLabel[data.status].tone} icon={data.status === "unavailable" ? CalendarX2 : CalendarCheck2}>
                {statusLabel[data.status].text}
              </Badge>
              {data.deadline && data.canEdit ? (
                <p className="flex items-center gap-2 text-sm text-ink-700">
                  <Clock3 className="size-4" aria-hidden />
                  Prazo para registrar: {formatDateTime(data.deadline)}
                </p>
              ) : null}
            </div>
            {!data.canEdit ? (
              <p className="max-w-md text-sm text-ink-700">
                {data.lockedReason ?? "O registro desta semana não está disponível para edição."}
              </p>
            ) : null}
          </Card>

          {!data.canEdit ? (
            readOnlySelected.length > 0 ? (
              <Card>
                <h2 className="font-display text-xl text-forest-900">Horários registrados</h2>
                <ul className="mt-4 space-y-2">
                  {readOnlySelected.map((option) => (
                    <li key={option.id} className="flex flex-wrap items-center gap-x-3 text-ink-800">
                      <span className="capitalize-first font-semibold">{formatDayLong(new Date(option.startsAt))}</span>
                      <span>{formatTimeRange(option.startsAt, option.endsAt)}</span>
                      <span className="text-ink-600">· {option.location.name}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null
          ) : (
            <Card className="space-y-8">
              <ol className="flex flex-wrap items-center gap-3" aria-label="Etapas">
                {steps.map((label, index) => {
                  const skipped = index === 1 && current.mode === "unavailable";
                  return (
                    <li
                      key={label}
                      aria-current={index === step ? "step" : undefined}
                      className={cn(
                        "flex items-center gap-2 text-sm font-semibold",
                        index === step ? "text-forest-900" : "text-ink-500",
                        skipped && "line-through opacity-60",
                      )}
                    >
                      <span
                        className={cn(
                          "grid size-8 place-items-center rounded-full text-xs",
                          index < step
                            ? "bg-forest-700 text-ivory"
                            : index === step
                              ? "bg-sage-200 text-forest-900"
                              : "bg-sand-100 text-ink-600",
                        )}
                      >
                        {index < step ? <Check className="size-4" aria-hidden /> : index + 1}
                      </span>
                      {label}
                      {index < steps.length - 1 ? <span className="mx-1 hidden h-px w-6 bg-line-strong sm:block" aria-hidden /> : null}
                    </li>
                  );
                })}
              </ol>

              {step === 0 ? (
                <fieldset className="space-y-3">
                  <legend className="font-display text-2xl text-forest-900">Como será sua semana?</legend>
                  {(
                    [
                      ["available", "Posso atender nesta semana", "Escolher os dias, horários e locais em que posso conduzir sessões."],
                      ["unavailable", "Estou indisponível nesta semana", "Declarar que não poderei conduzir sessões em nenhum horário."],
                    ] as const
                  ).map(([value, title, text]) => (
                    <label
                      key={value}
                      className="flex min-h-16 cursor-pointer items-start gap-4 rounded-2xl border border-line-strong bg-paper p-4 transition-colors hover:border-forest-300 has-checked:border-forest-600 has-checked:bg-forest-50 has-focus-visible:ring-4 has-focus-visible:ring-forest-600/15"
                    >
                      <input
                        type="radio"
                        name="mode"
                        value={value}
                        checked={current.mode === value}
                        onChange={() => update({ mode: value })}
                        className="mt-1 size-5 accent-forest-700"
                      />
                      <span>
                        <span className="block font-semibold text-forest-900">{title}</span>
                        <span className="block text-sm text-ink-600">{text}</span>
                      </span>
                    </label>
                  ))}
                </fieldset>
              ) : null}

              {step === 1 ? (
                <fieldset className="space-y-6">
                  <legend className="font-display text-2xl text-forest-900">Escolha os horários</legend>
                  <p className="text-sm text-ink-600">
                    Opções oferecidas pela coordenação para esta semana. Selecionados: {current.selected.length}
                  </p>
                  {days.length === 0 ? (
                    <Alert tone="info">A coordenação ainda não ofereceu horários para esta semana.</Alert>
                  ) : (
                    days.map(([key, options]) => (
                      <div key={key}>
                        <p className="capitalize-first mb-3 font-semibold text-forest-900">
                          {formatDayLong(new Date(options[0].startsAt))}
                        </p>
                        <div className="grid gap-3 sm:grid-cols-2">
                          {options.map((option) => (
                            <label
                              key={option.id}
                              className="flex min-h-16 cursor-pointer items-start gap-3 rounded-2xl border border-line-strong bg-paper p-4 transition-colors hover:border-forest-300 has-checked:border-forest-600 has-checked:bg-forest-50 has-focus-visible:ring-4 has-focus-visible:ring-forest-600/15"
                            >
                              <input
                                type="checkbox"
                                checked={current.selected.includes(option.id)}
                                onChange={() => toggle(option.id)}
                                className="mt-1 size-5 accent-forest-700"
                              />
                              <span>
                                <span className="block font-semibold text-forest-900">
                                  {formatTimeRange(option.startsAt, option.endsAt)}
                                </span>
                                <span className="mt-0.5 flex items-center gap-1.5 text-sm text-ink-600">
                                  <MapPin className="size-3.5" aria-hidden />
                                  {option.location.name}
                                </span>
                              </span>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                  {stepError ? <Alert tone="danger">{stepError}</Alert> : null}
                </fieldset>
              ) : null}

              {step === 2 ? (
                <div className="space-y-5">
                  <h2 className="font-display text-2xl text-forest-900">Confira antes de publicar</h2>
                  {current.mode === "unavailable" ? (
                    <Alert tone="info" title="Você declarará indisponibilidade">
                      Nenhum horário seu será oferecido na semana de {formatWeekRange(data.weekStart)}.
                    </Alert>
                  ) : (
                    <div className="rounded-2xl bg-sand-50 p-5">
                      <p className="font-semibold text-forest-900">
                        {plural(current.selected.length, "horário")} na semana de {formatWeekRange(data.weekStart)}
                      </p>
                      <ul className="mt-4 space-y-2.5">
                        {current.selected
                          .map((id) => optionById.get(id))
                          .filter((option): option is SlotOption => Boolean(option))
                          .sort((a, b) => a.startsAt.localeCompare(b.startsAt))
                          .map((option) => (
                            <li key={option.id} className="flex flex-wrap items-center gap-x-3 text-ink-800">
                              <span className="capitalize-first font-semibold">{formatDayLong(new Date(option.startsAt))}</span>
                              <span>{formatTime(option.startsAt)}</span>
                              <span className="text-ink-600">· {option.location.name}</span>
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                  <p className="text-sm text-ink-600">
                    O registro só vale depois que o sistema confirmar a publicação.
                  </p>
                  {publishError ? (
                    <Alert tone="danger" title="Não foi possível publicar">
                      {publishError}
                    </Alert>
                  ) : null}
                </div>
              ) : null}

              <div className="flex flex-col-reverse gap-3 border-t border-line pt-6 sm:flex-row sm:justify-between">
                <Button variant="secondary" onClick={back} disabled={step === 0 || publishing}>
                  Voltar
                </Button>
                {step < 2 ? (
                  <Button onClick={next}>Continuar</Button>
                ) : (
                  <Button
                    onClick={publish}
                    loading={publishing}
                    icon={<Send className="size-4" aria-hidden />}
                  >
                    {current.mode === "unavailable" ? "Registrar indisponibilidade" : "Publicar disponibilidade"}
                  </Button>
                )}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
