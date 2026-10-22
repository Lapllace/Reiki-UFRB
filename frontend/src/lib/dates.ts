/**
 * Utilitários de data (pt-BR, fuso local do navegador).
 *
 * IMPORTANTE (Cache Components): nunca chame `new Date()` / `Date.now()` durante
 * a renderização de componentes. Use `useNow()` (src/lib/hooks/use-now.ts), que
 * só entrega o horário depois da hidratação.
 */

const pad = (value: number) => String(value).padStart(2, "0");

export function toISODate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Converte "YYYY-MM-DD" em Date local à meia-noite. */
export function parseISODate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function addDays(date: Date, amount: number): Date {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + amount);
  return copy;
}

/** Primeiro dia da semana (segunda-feira). A definição oficial é do backend. */
export function startOfWeek(date: Date): Date {
  const copy = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const offset = (copy.getDay() + 6) % 7;
  copy.setDate(copy.getDate() - offset);
  return copy;
}

export function addWeeks(weekStart: string, amount: number): string {
  return toISODate(addDays(parseISODate(weekStart), amount * 7));
}

export function weekDays(weekStart: string): string[] {
  const start = parseISODate(weekStart);
  return Array.from({ length: 7 }, (_, index) => toISODate(addDays(start, index)));
}

/** Chave "YYYY-MM-DD" (fuso local) de um instante ISO. */
export function localDateKey(iso: string): string {
  return toISODate(new Date(iso));
}

const weekdayLong = new Intl.DateTimeFormat("pt-BR", { weekday: "long" });
const weekdayShort = new Intl.DateTimeFormat("pt-BR", { weekday: "short" });
const dayMonth = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "long" });
const dayMonthShort = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "short" });
const monthLong = new Intl.DateTimeFormat("pt-BR", { month: "long" });
const dateTimeFmt = new Intl.DateTimeFormat("pt-BR", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const timeFmt = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const strip = (value: string) => value.replace(".", "");

export function weekdayName(date: Date): string {
  return weekdayLong.format(date);
}

export function weekdayAbbr(date: Date): string {
  return strip(weekdayShort.format(date));
}

export function formatDayMonth(date: Date): string {
  return dayMonth.format(date);
}

export function formatDayLong(date: Date): string {
  return `${weekdayLong.format(date)}, ${dayMonth.format(date)}`;
}

export function formatTime(iso: string): string {
  return timeFmt.format(new Date(iso));
}

export function formatTimeRange(startIso: string, endIso: string): string {
  return `${formatTime(startIso)} – ${formatTime(endIso)}`;
}

export function formatDateTime(iso: string): string {
  return strip(dateTimeFmt.format(new Date(iso)));
}

/** "19 – 25 de outubro de 2026" ou "26 de out. – 1 de nov. de 2026". */
export function formatWeekRange(weekStart: string): string {
  const start = parseISODate(weekStart);
  const end = addDays(start, 6);
  const sameMonth = start.getMonth() === end.getMonth();
  const year = end.getFullYear();
  if (sameMonth) {
    return `${start.getDate()} – ${end.getDate()} de ${monthLong.format(end)} de ${year}`;
  }
  return `${strip(dayMonthShort.format(start))} – ${strip(dayMonthShort.format(end))} de ${year}`;
}

/** "hoje", "amanhã", "em 3 dias" — relativo ao dia civil local. */
export function relativeDayLabel(iso: string, now: Date): string {
  const target = new Date(iso);
  const a = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const b = new Date(target.getFullYear(), target.getMonth(), target.getDate()).getTime();
  const diff = Math.round((b - a) / 86_400_000);
  if (diff === 0) return "hoje";
  if (diff === 1) return "amanhã";
  if (diff === -1) return "ontem";
  if (diff > 1) return `em ${diff} dias`;
  return `há ${Math.abs(diff)} dias`;
}

export function isPast(iso: string, now: Date): boolean {
  return new Date(iso).getTime() < now.getTime();
}
