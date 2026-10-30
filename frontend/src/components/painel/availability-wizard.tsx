"use client";

import { useMemo, useRef, useState } from "react";
import {
  CalendarCheck2,
  CalendarX2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  MapPin,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SelectField, TextAreaField, TextField } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/section";
import { ErrorState, LoadingBlock } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { toApiError } from "@/lib/api/errors";
import {
  addWeeks,
  formatDateTime,
  formatDayLong,
  formatTimeRange,
  formatWeekRange,
} from "@/lib/dates";
import { plural } from "@/lib/format";
import { useAccountResource } from "@/lib/hooks/use-account-resource";
import type { AvailabilityEntry, Location, WeeklyAvailability } from "@/lib/types";

type Mode = "available" | "unavailable";

interface EntryDraft {
  id: string;
  date: string;
  startsAt: string;
  endsAt: string;
  locationId: string;
  note: string;
}

interface Draft {
  key: string;
  mode: Mode;
  entries: EntryDraft[];
  note: string;
}

const statusLabel: Record<WeeklyAvailability["status"], { text: string; tone: "sage" | "forest" | "honey" }> = {
  pending: { text: "Ainda não registrada", tone: "honey" },
  submitted: { text: "Disponibilidade registrada", tone: "forest" },
  unavailable: { text: "Indisponibilidade declarada", tone: "sage" },
};

function localInputValue(iso: string): string {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toEntryDraft(entry: AvailabilityEntry): EntryDraft {
  const start = localInputValue(entry.startsAt);
  const end = localInputValue(entry.endsAt);
  return {
    id: entry.id,
    date: start.slice(0, 10),
    startsAt: start.slice(11, 16),
    endsAt: end.slice(11, 16),
    locationId: entry.locationId ?? "",
    note: entry.note ?? "",
  };
}

function toISO(date: string, time: string): string {
  return new Date(`${date}T${time}`).toISOString();
}

function blankEntry(weekStart: string, id: string): EntryDraft {
  return {
    id,
    date: weekStart,
    startsAt: "09:00",
    endsAt: "10:00",
    locationId: "",
    note: "",
  };
}

function entryLabel(entry: EntryDraft, locations: Location[]): string {
  const location = locations.find((item) => item.id === entry.locationId);
  return `${formatDayLong(new Date(`${entry.date}T12:00:00`))} · ${entry.startsAt} – ${entry.endsAt}${location ? ` · ${location.name}` : ""}`;
}

function groupByDay(entries: EntryDraft[]) {
  return [...entries].sort((a, b) => `${a.date}${a.startsAt}`.localeCompare(`${b.date}${b.startsAt}`));
}

export function AvailabilityWizard() {
  const toast = useToast();
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [confirmedWeek, setConfirmedWeek] = useState<string | null>(null);
  const entryCounter = useRef(0);

  const availability = useAccountResource(
    `availability:${weekStart ?? "open"}`,
    (signal) => api.availability.get(weekStart, signal),
  );
  const locations = useAccountResource("locations", (signal) => api.locations.list(signal));

  const current: Draft | null = useMemo(() => {
    if (!availability.data) return null;
    if (draft?.key === availability.data.weekStart) return draft;
    return {
      key: availability.data.weekStart,
      mode: availability.data.status === "unavailable" ? "unavailable" : "available",
      entries: availability.data.entries.map(toEntryDraft),
      note: availability.data.note ?? "",
    };
  }, [availability.data, draft]);

  const locationRows = locations.data ?? [];
  const readOnlyEntries = availability.data?.entries ?? [];
  const combinedError = availability.error ?? locations.error;

  function navigate(delta: number) {
    if (!availability.data) return;
    setWeekStart(addWeeks(availability.data.weekStart, delta));
    setDraft(null);
    setPublishError(null);
    setConfirmedWeek(null);
  }

  function update(partial: Partial<Draft>) {
    if (!availability.data || !current) return;
    setDraft({ ...current, ...partial });
    setPublishError(null);
  }

  function updateEntry(id: string, partial: Partial<EntryDraft>) {
    if (!current) return;
    update({ entries: current.entries.map((entry) => (entry.id === id ? { ...entry, ...partial } : entry)) });
  }

  function addEntry() {
    if (!availability.data || !current) return;
    entryCounter.current += 1;
    update({
      mode: "available",
      entries: [...current.entries, blankEntry(availability.data.weekStart, `draft-${entryCounter.current}`)],
    });
  }

  function removeEntry(id: string) {
    if (!current) return;
    update({ entries: current.entries.filter((entry) => entry.id !== id) });
  }

  function validateEntries(entries: EntryDraft[]): string | null {
    if (entries.length === 0) return "Adicione ao menos um intervalo ou declare indisponibilidade.";
    for (const [index, entry] of entries.entries()) {
      if (!entry.date || !entry.startsAt || !entry.endsAt) {
        return `Preencha a data, o início e o fim do intervalo ${index + 1}.`;
      }
      if (new Date(`${entry.date}T${entry.endsAt}`).getTime() <= new Date(`${entry.date}T${entry.startsAt}`).getTime()) {
        return `O fim deve ser posterior ao início no intervalo ${index + 1}.`;
      }
    }
    return null;
  }

  async function publish() {
    if (!availability.data || !current) return;
    const validationError = current.mode === "unavailable" ? null : validateEntries(current.entries);
    if (validationError) {
      setPublishError(validationError);
      return;
    }
    setPublishing(true);
    setPublishError(null);
    try {
      const saved = await api.availability.publish({
        weekStart: availability.data.weekStart,
        unavailable: current.mode === "unavailable",
        note: current.note.trim() || null,
        entries:
          current.mode === "unavailable"
            ? []
            : current.entries.map((entry) => ({
                startsAt: toISO(entry.date, entry.startsAt),
                endsAt: toISO(entry.date, entry.endsAt),
                locationId: entry.locationId || null,
                note: entry.note.trim() || null,
              })),
      });
      setDraft(null);
      setConfirmedWeek(saved.weekStart);
      toast.push({
        tone: "success",
        title: saved.status === "unavailable" ? "Indisponibilidade registrada" : "Disponibilidade registrada",
        message: "O sistema confirmou o seu registro.",
      });
      availability.reload();
    } catch (caught) {
      setPublishError(toApiError(caught).message);
    } finally {
      setPublishing(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Ministrante"
        title="Disponibilidade semanal"
        description="Informe os dias, horários e locais em que você pode conduzir sessões ou declare indisponibilidade para a semana."
      />

      <div className="flex items-center gap-2" role="group" aria-label="Navegar entre semanas">
        <Button
          variant="secondary"
          size="sm"
          className="size-11 px-0!"
          aria-label="Semana anterior"
          disabled={!availability.data}
          onClick={() => navigate(-1)}
        >
          <ChevronLeft className="size-5" aria-hidden />
        </Button>
        <div className="min-w-0 flex-1 px-2 text-center sm:max-w-sm sm:flex-none">
          <p className="eyebrow">Semana</p>
          <p className="mt-1.5 font-display text-xl text-forest-900 sm:text-2xl" aria-live="polite">
            {availability.data ? formatWeekRange(availability.data.weekStart) : "Carregando…"}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="size-11 px-0!"
          aria-label="Próxima semana"
          disabled={!availability.data}
          onClick={() => navigate(1)}
        >
          <ChevronRight className="size-5" aria-hidden />
        </Button>
        {availability.refreshing ? <span className="ml-2 text-sm text-ink-600">Atualizando…</span> : null}
      </div>

      {combinedError ? (
        <ErrorState error={combinedError} onRetry={() => { availability.reload(); locations.reload(); }} />
      ) : availability.loading || !availability.data || !current || locations.loading ? (
        <LoadingBlock rows={2} label="Carregando disponibilidade e locais…" />
      ) : (
        <>
          {confirmedWeek === availability.data.weekStart ? (
            <Alert tone="success" title="Registro confirmado pelo sistema" onDismiss={() => setConfirmedWeek(null)}>
              A resposta do servidor confirmou a atualização desta semana.
            </Alert>
          ) : null}

          <Card className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-2">
              <Badge
                tone={statusLabel[availability.data.status].tone}
                icon={availability.data.status === "unavailable" ? CalendarX2 : CalendarCheck2}
              >
                {statusLabel[availability.data.status].text}
              </Badge>
              {availability.data.submittedAt ? (
                <p className="flex items-center gap-2 text-sm text-ink-700">
                  <Clock3 className="size-4" aria-hidden />
                  Registrada em {formatDateTime(availability.data.submittedAt)}
                </p>
              ) : null}
            </div>
            {!availability.data.canEdit ? (
              <p className="max-w-md text-sm text-ink-700">
                {availability.data.lockedReason ?? "O registro desta semana não está disponível para edição."}
              </p>
            ) : null}
          </Card>

          {!availability.data.canEdit ? (
            availability.data.status === "unavailable" ? (
              <Card>
                <h2 className="font-display text-xl text-forest-900">Indisponibilidade registrada</h2>
                <p className="mt-2 text-ink-700">Nenhum intervalo foi informado para esta semana.</p>
              </Card>
            ) : (
              <Card>
                <h2 className="font-display text-xl text-forest-900">Horários registrados</h2>
                <ul className="mt-4 space-y-3">
                  {readOnlyEntries.map((entry) => (
                    <li key={entry.id} className="flex flex-wrap items-center gap-x-3 text-ink-800">
                      <span className="capitalize-first font-semibold">{formatDayLong(new Date(entry.startsAt))}</span>
                      <span>{formatTimeRange(entry.startsAt, entry.endsAt)}</span>
                      {entry.locationId ? (
                        <span className="flex items-center gap-1.5 text-ink-600">
                          <MapPin className="size-3.5" aria-hidden />
                          {locationRows.find((location) => location.id === entry.locationId)?.name ?? "Local informado"}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </Card>
            )
          ) : (
            <Card className="space-y-8">
              <fieldset className="space-y-3">
                <legend className="font-display text-2xl text-forest-900">Como será sua semana?</legend>
                {([
                  ["available", "Posso atender nesta semana", "Informe cada intervalo em que pode conduzir sessões."],
                  ["unavailable", "Estou indisponível nesta semana", "Declare que não poderá conduzir sessões em nenhum horário."],
                ] as const).map(([value, title, text]) => (
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

              {current.mode === "available" ? (
                <fieldset className="space-y-5">
                  <legend className="font-display text-2xl text-forest-900">Seus intervalos</legend>
                  <p className="text-sm text-ink-600">
                    Adicione, edite ou remova intervalos antes de enviar. O local é opcional.
                  </p>
                  {current.entries.length ? (
                    <div className="space-y-4">
                      {groupByDay(current.entries).map((entry) => (
                        <div key={entry.id} className="rounded-2xl border border-line-strong bg-paper p-4">
                          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            <TextField
                              label="Data"
                              type="date"
                              value={entry.date}
                              onChange={(event) => updateEntry(entry.id, { date: event.target.value })}
                            />
                            <TextField
                              label="Início"
                              type="time"
                              value={entry.startsAt}
                              onChange={(event) => updateEntry(entry.id, { startsAt: event.target.value })}
                            />
                            <TextField
                              label="Fim"
                              type="time"
                              value={entry.endsAt}
                              onChange={(event) => updateEntry(entry.id, { endsAt: event.target.value })}
                            />
                            <SelectField
                              label="Local"
                              value={entry.locationId}
                              onChange={(event) => updateEntry(entry.id, { locationId: event.target.value })}
                            >
                              <option value="">Sem local definido</option>
                              {locationRows.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}
                            </SelectField>
                          </div>
                          <div className="mt-4 flex flex-wrap items-end gap-3">
                            <TextField
                              label="Observação"
                              value={entry.note}
                              onChange={(event) => updateEntry(entry.id, { note: event.target.value })}
                              className="min-w-64"
                            />
                            <Button variant="ghost" size="sm" onClick={() => removeEntry(entry.id)} icon={<Trash2 className="size-4" aria-hidden />}>
                              Remover
                            </Button>
                          </div>
                          <p className="mt-3 text-sm text-ink-600">{entryLabel(entry, locationRows)}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Alert tone="info">Nenhum intervalo foi adicionado ainda.</Alert>
                  )}
                  <Button variant="secondary" onClick={addEntry} icon={<Plus className="size-4" aria-hidden />}>
                    Adicionar intervalo
                  </Button>
                </fieldset>
              ) : (
                <Alert tone="info" title="Indisponibilidade semanal">
                  Ao enviar, o servidor receberá explicitamente <code>entries: []</code>.
                </Alert>
              )}

              <TextAreaField
                label="Observação da semana"
                value={current.note}
                onChange={(event) => update({ note: event.target.value })}
                hint="Opcional."
              />

              {publishError ? <Alert tone="danger" title="Não foi possível registrar">{publishError}</Alert> : null}
              <div className="flex justify-end border-t border-line pt-6">
                <Button onClick={publish} loading={publishing} icon={<Save className="size-4" aria-hidden />}>
                  {current.mode === "unavailable" ? "Registrar indisponibilidade" : `Registrar ${plural(current.entries.length, "intervalo")}`}
                </Button>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
