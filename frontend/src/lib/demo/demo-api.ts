/**
 * DEMONSTRAÇÃO — implementação FICTÍCIA de `ReikiApi`, em memória.
 *
 * Existe apenas para permitir testar telas e estados sem backend. Só é
 * importada dinamicamente quando IS_DEMO é verdadeiro (desenvolvimento).
 * Não persiste nada e NÃO deve ser tratada como autenticação, agendamento ou
 * confirmação reais. As "regras" abaixo (prazos de cancelamento etc.) são
 * apenas ilustrativas para exercitar a interface.
 */
import type { ReikiApi } from "@/lib/api/contract";
import { ApiError, fallbackMessage } from "@/lib/api/errors";
import { addDays, parseISODate, toISODate, weekDays } from "@/lib/dates";
import { plural } from "@/lib/format";
import type {
  AcceptCoverResult,
  AuditEvent,
  CoverInvite,
  CoverRequest,
  Enrollment,
  InstructorSession,
  Location,
  Reallocation,
  Role,
  RosterEntry,
  Session,
  WeekSessions,
  WeeklyAvailability,
  WeeklyCycle,
} from "@/lib/types";
import { getControls } from "./demo-controls";
import {
  AVAILABILITY_TEMPLATES,
  DEMO_INSTRUCTORS,
  DEMO_LOCATIONS,
  DEMO_PARTICIPANT_NAMES,
  DEMO_USERS,
  OPEN_AVAILABILITY_WEEK_OFFSET,
  createDemoState,
  type AvailabilityRecord,
  type CoverRequestRecord,
  type DemoState,
  type EnrollmentRecord,
  type InviteRecord,
  type ReallocationRecord,
  type SessionRecord,
} from "./demo-store";

let state: DemoState | null = null;
const store = (): DemoState => (state ??= createDemoState());

const HOUR = 3_600_000;
const MY_INSTRUCTOR_ID = DEMO_INSTRUCTORS.i1.id;
const ALL_INSTRUCTORS = Object.values(DEMO_INSTRUCTORS);

/* ------------------------------ infraestrutura ----------------------------- */

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

/** Simula latência, falha de rede opcional e checagem de perfil (como um servidor faria). */
async function gate(options: { role?: Role; auth?: boolean; signal?: AbortSignal } = {}) {
  await wait(380 + Math.random() * 260, options.signal);
  const controls = getControls();
  if (controls.simulateError) {
    throw new ApiError("network", fallbackMessage("network"));
  }
  if (options.role || options.auth) {
    if (controls.profile === "visitor") {
      throw new ApiError("unauthenticated", fallbackMessage("unauthenticated"), { status: 401 });
    }
    if (options.role && controls.profile !== options.role) {
      throw new ApiError("forbidden", fallbackMessage("forbidden"), { status: 403 });
    }
  }
}

function fail(kind: ApiError["kind"], message: string, status: number, code?: string): never {
  throw new ApiError(kind, message, { status, code: code ?? null });
}

/* -------------------------------- conversões ------------------------------- */

const locationById = (id: string): Location =>
  DEMO_LOCATIONS.find((location) => location.id === id) ?? DEMO_LOCATIONS[0];

const instructorById = (id: string | null) =>
  id ? (ALL_INSTRUCTORS.find((instructor) => instructor.id === id) ?? null) : null;

function derivedStatus(record: SessionRecord): Session["status"] {
  if (record.status === "cancelled") return "cancelled";
  if (new Date(record.endsAt).getTime() < Date.now()) return "completed";
  if (record.status === "open" || record.status === "full") {
    return record.confirmedCount >= record.capacity ? "full" : "open";
  }
  return record.status;
}

function activeEnrollmentFor(sessionId: string): EnrollmentRecord | undefined {
  return [...store().enrollments.values()].find(
    (enrollment) => enrollment.sessionId === sessionId && enrollment.status !== "cancelled",
  );
}

function toSession(record: SessionRecord): Session {
  const mine = getControls().profile === "participant" ? activeEnrollmentFor(record.id) : undefined;
  const status = derivedStatus(record);
  return {
    id: record.id,
    startsAt: record.startsAt,
    endsAt: record.endsAt,
    location: locationById(record.locationId),
    instructor: instructorById(record.instructorId),
    capacity: record.capacity,
    confirmedCount: record.confirmedCount,
    waitlistCount: record.waitlistCount,
    waitlistEnabled: true,
    status,
    isExtra: record.isExtra,
    enrollmentOpensAt: record.enrollmentOpensAt,
    notices: record.notices,
    myEnrollment: mine
      ? {
          id: mine.id,
          status: mine.status === "confirmed" && status === "completed" ? "attended" : mine.status,
          waitlistPosition: mine.waitlistPosition,
        }
      : null,
  };
}

function sessionOrThrow(id: string): SessionRecord {
  const record = store().sessions.get(id);
  if (!record) fail("not_found", "Sessão não encontrada.", 404);
  return record;
}

function toEnrollment(record: EnrollmentRecord): Enrollment {
  const session = sessionOrThrow(record.sessionId);
  const sessionStatus = derivedStatus(session);
  const status =
    record.status === "confirmed" && sessionStatus === "completed" ? "attended" : record.status;
  const active = status === "confirmed" || status === "waitlisted";
  const hoursLeft = (new Date(session.startsAt).getTime() - Date.now()) / HOUR;
  const canCancel = active && sessionStatus !== "completed" && hoursLeft > 2;
  return {
    id: record.id,
    status,
    waitlistPosition: record.waitlistPosition,
    createdAt: record.createdAt,
    cancelledAt: record.cancelledAt,
    session: toSession(session),
    canCancel,
    cancelBlockedReason:
      active && !canCancel
        ? "O cancelamento não está mais disponível para esta sessão (regra de demonstração)."
        : null,
  };
}

function weekRange(weekStart: string): { start: number; end: number } {
  const start = parseISODate(weekStart);
  return { start: start.getTime(), end: addDays(start, 7).getTime() };
}

function sessionsOfWeek(weekStart: string): SessionRecord[] {
  const { start, end } = weekRange(weekStart);
  return [...store().sessions.values()]
    .filter((record) => {
      const time = new Date(record.startsAt).getTime();
      return time >= start && time < end;
    })
    .sort((a, b) => a.startsAt.localeCompare(b.startsAt));
}

function weekOffset(weekStart: string): number {
  const diff = parseISODate(weekStart).getTime() - store().mondayOfThisWeek.getTime();
  return Math.round(diff / (7 * 24 * HOUR));
}

function hash(text: string): number {
  let value = 0;
  for (const char of text) value = (value * 31 + char.charCodeAt(0)) >>> 0;
  return value;
}

function buildRoster(record: SessionRecord): RosterEntry[] {
  const pool = DEMO_PARTICIPANT_NAMES;
  const base = hash(record.id);
  const completed = derivedStatus(record) === "completed";
  const mine = [...store().enrollments.values()].find(
    (enrollment) => enrollment.sessionId === record.id && enrollment.status !== "cancelled",
  );
  const entries: RosterEntry[] = [];
  for (let index = 0; index < record.confirmedCount; index += 1) {
    entries.push({
      enrollmentId: `r-${record.id}-${index}`,
      participantName: pool[(base + index) % pool.length],
      status: completed ? "attended" : "confirmed",
    });
  }
  for (let index = 0; index < record.waitlistCount; index += 1) {
    entries.push({
      enrollmentId: `r-${record.id}-w${index}`,
      participantName: pool[(base + index + 7) % pool.length],
      status: "waitlisted",
      waitlistPosition: index + 1,
    });
  }
  if (mine) {
    const slot =
      mine.status === "waitlisted"
        ? entries.findIndex((entry) => entry.waitlistPosition === (mine.waitlistPosition ?? 1))
        : 0;
    if (slot >= 0 && entries[slot]) {
      entries[slot] = { ...entries[slot], participantName: DEMO_USERS.participant.name };
    }
  }
  return entries;
}

function pushEvent(
  kind: AuditEvent["kind"],
  description: string,
  actor: string | null,
  sessionId?: string,
) {
  const current = store();
  current.counters.event += 1;
  current.events.unshift({
    id: `ev-${current.counters.event}`,
    kind,
    at: new Date().toISOString(),
    description,
    actor,
    sessionId: sessionId ?? null,
  });
}

function toCoverInvite(record: InviteRecord): CoverInvite {
  return {
    id: record.id,
    status: record.status,
    session: toSession(sessionOrThrow(record.sessionId)),
    createdAt: record.createdAt,
    expiresAt: null,
    acceptedBy: instructorById(record.acceptedById),
  };
}

function toCoverRequest(record: CoverRequestRecord): CoverRequest {
  const { sessionId, ...rest } = record;
  return { ...rest, session: toSession(sessionOrThrow(sessionId)) };
}

function toReallocation(record: ReallocationRecord): Reallocation {
  const { originSessionId, candidateSessionIds, appliedToId, ...rest } = record;
  return {
    ...rest,
    originSession: toSession(sessionOrThrow(originSessionId)),
    candidateSessions: candidateSessionIds.map((id) => toSession(sessionOrThrow(id))),
    appliedTo: appliedToId ? toSession(sessionOrThrow(appliedToId)) : null,
  };
}

function toInstructorSession(record: SessionRecord): InstructorSession {
  const status = derivedStatus(record);
  const hoursLeft = (new Date(record.startsAt).getTime() - Date.now()) / HOUR;
  const cancellable = (status === "open" || status === "full") && hoursLeft > 24;
  return {
    session: toSession(record),
    canCancel: cancellable,
    cancelBlockedReason:
      !cancellable && (status === "open" || status === "full")
        ? "Cancelamentos com menos de 24 horas de antecedência devem ser tratados com a coordenação (regra de demonstração)."
        : null,
  };
}

function availabilityRecord(weekStart: string, instructorId: string): AvailabilityRecord {
  const current = store();
  const row = current.availability.get(weekStart);
  return (
    row?.get(instructorId) ?? { status: "pending", submittedAt: null, selectedSlotIds: [] }
  );
}

function buildAvailability(weekStart: string): WeeklyAvailability {
  const offset = weekOffset(weekStart);
  const start = parseISODate(weekStart);
  const record = availabilityRecord(weekStart, MY_INSTRUCTOR_ID);
  const canEdit = offset === OPEN_AVAILABILITY_WEEK_OFFSET;
  const monday = store().mondayOfThisWeek;
  return {
    weekStart,
    weekEnd: toISODate(addDays(start, 6)),
    status: record.status,
    deadline: canEdit
      ? new Date(
          monday.getFullYear(),
          monday.getMonth(),
          monday.getDate() + 9,
          18,
        ).toISOString()
      : null,
    canEdit,
    lockedReason: canEdit
      ? null
      : offset < OPEN_AVAILABILITY_WEEK_OFFSET
        ? "O registro de disponibilidade desta semana já foi encerrado."
        : "O registro para esta semana ainda não foi aberto pela coordenação.",
    options: AVAILABILITY_TEMPLATES.map((template, index) => {
      const startsAt = new Date(
        start.getFullYear(),
        start.getMonth(),
        start.getDate() + template.day,
        template.hour,
      );
      return {
        id: `opt-${weekStart}-${index}`,
        startsAt: startsAt.toISOString(),
        endsAt: new Date(startsAt.getTime() + HOUR).toISOString(),
        location: locationById(template.loc),
      };
    }),
    selectedSlotIds: record.selectedSlotIds,
  };
}

function assertValidWeek(weekStart: string) {
  if (Number.isNaN(parseISODate(weekStart).getTime())) {
    fail("validation", "Semana inválida.", 422);
  }
}

/* ---------------------------------- API ---------------------------------- */

export const demoApi: ReikiApi = {
  auth: {
    async me() {
      await wait(250);
      const { profile } = getControls();
      return profile === "visitor" ? null : DEMO_USERS[profile];
    },
    async login() {
      await wait(250);
      return fail(
        "validation",
        "No modo de demonstração não há login real. Escolha um perfil na barra de demonstração.",
        400,
      );
    },
    async logout() {
      await wait(150);
    },
  },

  locations: {
    async list(signal) {
      await gate({ signal });
      return DEMO_LOCATIONS;
    },
  },

  sessions: {
    async listWeek(weekStart, signal): Promise<WeekSessions> {
      await gate({ signal });
      assertValidWeek(weekStart);
      const records = sessionsOfWeek(weekStart);
      return {
        weekStart,
        weekEnd: weekDays(weekStart)[6],
        sessions: records.map(toSession),
        published: records.length > 0,
      };
    },
  },

  enrollments: {
    async create(sessionId) {
      await gate({ role: "participant" });
      const current = store();
      const record = sessionOrThrow(sessionId);
      const status = derivedStatus(record);
      if (activeEnrollmentFor(sessionId)) {
        fail("conflict", "Você já possui inscrição nesta sessão.", 409, "already_enrolled");
      }
      if (status !== "open" && status !== "full") {
        fail("conflict", "Esta sessão não está aceitando inscrições.", 409, "not_open");
      }
      current.counters.enrollment += 1;
      const id = `enr-${current.counters.enrollment}`;
      const confirmed = record.confirmedCount < record.capacity;
      const waitlistPosition = confirmed ? null : record.waitlistCount + 1;
      if (confirmed) record.confirmedCount += 1;
      else record.waitlistCount += 1;
      const enrollment: EnrollmentRecord = {
        id,
        sessionId,
        status: confirmed ? "confirmed" : "waitlisted",
        waitlistPosition,
        createdAt: new Date().toISOString(),
        cancelledAt: null,
      };
      current.enrollments.set(id, enrollment);
      return { enrollment: toEnrollment(enrollment) };
    },
    async listMine(signal) {
      await gate({ role: "participant", signal });
      return [...store().enrollments.values()]
        .sort((a, b) => sessionOrThrow(a.sessionId).startsAt.localeCompare(sessionOrThrow(b.sessionId).startsAt))
        .map(toEnrollment);
    },
    async cancel(enrollmentId) {
      await gate({ role: "participant" });
      const record = store().enrollments.get(enrollmentId);
      if (!record) fail("not_found", "Inscrição não encontrada.", 404);
      const view = toEnrollment(record);
      if (!view.canCancel) {
        fail(
          "conflict",
          view.cancelBlockedReason ?? "Esta inscrição não pode mais ser cancelada.",
          409,
          "cancel_not_allowed",
        );
      }
      const session = sessionOrThrow(record.sessionId);
      if (record.status === "confirmed") session.confirmedCount = Math.max(0, session.confirmedCount - 1);
      if (record.status === "waitlisted") session.waitlistCount = Math.max(0, session.waitlistCount - 1);
      record.status = "cancelled";
      record.waitlistPosition = null;
      record.cancelledAt = new Date().toISOString();
      return toEnrollment(record);
    },
  },

  notifications: {
    async list(signal) {
      await gate({ role: "participant", signal });
      return [...store().notifications].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    },
    async markRead(id) {
      await gate({ role: "participant" });
      const item = store().notifications.find((notification) => notification.id === id);
      if (item) item.read = true;
    },
  },

  availability: {
    async get(weekStart, signal) {
      await gate({ role: "instructor", signal });
      const target =
        weekStart ?? toISODate(addDays(store().mondayOfThisWeek, OPEN_AVAILABILITY_WEEK_OFFSET * 7));
      assertValidWeek(target);
      return buildAvailability(target);
    },
    async publish(input) {
      await gate({ role: "instructor" });
      assertValidWeek(input.weekStart);
      const view = buildAvailability(input.weekStart);
      if (!view.canEdit) {
        fail("conflict", view.lockedReason ?? "Registro indisponível para esta semana.", 409);
      }
      if (!input.unavailable && input.slotIds.length === 0) {
        fail("validation", "Selecione ao menos um horário ou declare indisponibilidade.", 422);
      }
      const validIds = new Set(view.options.map((option) => option.id));
      if (input.slotIds.some((id) => !validIds.has(id))) {
        fail("validation", "Um dos horários escolhidos não é válido para esta semana.", 422);
      }
      const current = store();
      const row = current.availability.get(input.weekStart) ?? new Map();
      row.set(MY_INSTRUCTOR_ID, {
        status: input.unavailable ? "unavailable" : "published",
        submittedAt: new Date().toISOString(),
        selectedSlotIds: input.unavailable ? [] : input.slotIds,
      } satisfies AvailabilityRecord);
      current.availability.set(input.weekStart, row);
      pushEvent(
        "availability",
        input.unavailable
          ? `${DEMO_INSTRUCTORS.i1.name} declarou indisponibilidade para a semana de ${input.weekStart}.`
          : `${DEMO_INSTRUCTORS.i1.name} publicou ${plural(input.slotIds.length, "horário")} para a semana de ${input.weekStart}.`,
        DEMO_INSTRUCTORS.i1.name,
      );
      return buildAvailability(input.weekStart);
    },
  },

  instructor: {
    async listSessions(signal) {
      await gate({ role: "instructor", signal });
      return [...store().sessions.values()]
        .filter((record) => record.instructorId === MY_INSTRUCTOR_ID)
        .sort((a, b) => a.startsAt.localeCompare(b.startsAt))
        .map(toInstructorSession);
    },
    async roster(sessionId, signal) {
      await gate({ role: "instructor", signal });
      const record = sessionOrThrow(sessionId);
      if (record.instructorId !== MY_INSTRUCTOR_ID) {
        fail("forbidden", "Você só pode ver as inscrições das sessões que ministra.", 403);
      }
      return buildRoster(record);
    },
    async cancelSession(sessionId, reason) {
      await gate({ role: "instructor" });
      const record = sessionOrThrow(sessionId);
      if (record.instructorId !== MY_INSTRUCTOR_ID) {
        fail("forbidden", "Você só pode cancelar sessões que ministra.", 403);
      }
      const view = toInstructorSession(record);
      if (!view.canCancel) {
        fail("conflict", view.cancelBlockedReason ?? "Esta sessão não pode ser cancelada.", 409);
      }
      if (reason.trim().length < 10) {
        fail("validation", "Informe um motivo com pelo menos 10 caracteres.", 422);
      }
      const current = store();
      record.status = "needs_cover";
      record.notices = [
        {
          kind: "needs_cover",
          message: "O ministrante cancelou. A solicitação de cobertura foi enviada aos ministrantes elegíveis.",
        },
      ];
      current.coverRequests.unshift({
        id: `cr-${current.counters.event + 1}`,
        status: "open",
        sessionId,
        originalInstructor: DEMO_INSTRUCTORS.i1,
        reason: reason.trim(),
        invitedCount: ALL_INSTRUCTORS.length - 1,
        createdAt: new Date().toISOString(),
      });
      pushEvent(
        "cancellation",
        `${DEMO_INSTRUCTORS.i1.name} cancelou uma sessão. Cobertura solicitada a ${ALL_INSTRUCTORS.length - 1} ministrantes elegíveis.`,
        DEMO_INSTRUCTORS.i1.name,
        sessionId,
      );
      return toInstructorSession(record);
    },
    async listCoverInvites(signal) {
      await gate({ role: "instructor", signal });
      return [...store().invites.values()]
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        .map(toCoverInvite);
    },
    async acceptCover(inviteId): Promise<AcceptCoverResult> {
      await gate({ role: "instructor" });
      const current = store();
      const invite = current.invites.get(inviteId);
      if (!invite) fail("not_found", "Convite não encontrado.", 404);
      const session = sessionOrThrow(invite.sessionId);

      if (invite.status === "accepted") {
        return { outcome: "accepted", invite: toCoverInvite(invite) };
      }
      if (invite.status === "taken") {
        return { outcome: "already_taken", invite: toCoverInvite(invite) };
      }
      if (invite.status === "expired" || invite.status === "withdrawn") {
        return { outcome: "expired", invite: toCoverInvite(invite) };
      }

      // Cenário de demonstração: outro ministrante aceitou primeiro.
      const lostRace = invite.simulateLostRace || session.instructorId !== null;
      const request = current.coverRequests.find((item) => item.sessionId === invite.sessionId);
      if (lostRace) {
        const winner = session.instructorId ?? DEMO_INSTRUCTORS.i3.id;
        invite.status = "taken";
        invite.acceptedById = winner;
        session.instructorId = winner;
        session.status = "open";
        session.notices = [
          {
            kind: "instructor_changed",
            message: `Ministrante alterado: ${instructorById(winner)?.name ?? "outro ministrante"} assumiu a sessão.`,
          },
        ];
        if (request) {
          request.status = "covered";
          request.coveredBy = instructorById(winner);
          request.resolvedAt = new Date().toISOString();
        }
        pushEvent(
          "cover",
          `${instructorById(winner)?.name ?? "Outro ministrante"} assumiu a sessão (primeiro aceite registrado).`,
          instructorById(winner)?.name ?? null,
          invite.sessionId,
        );
        return { outcome: "already_taken", invite: toCoverInvite(invite) };
      }

      invite.status = "accepted";
      invite.acceptedById = MY_INSTRUCTOR_ID;
      session.instructorId = MY_INSTRUCTOR_ID;
      session.status = "open";
      session.notices = [
        {
          kind: "instructor_changed",
          message: `Ministrante alterado: ${DEMO_INSTRUCTORS.i1.name} assumiu a sessão.`,
        },
      ];
      if (request) {
        request.status = "covered";
        request.coveredBy = DEMO_INSTRUCTORS.i1;
        request.resolvedAt = new Date().toISOString();
      }
      for (const other of current.invites.values()) {
        if (other.sessionId === invite.sessionId && other.id !== invite.id && other.status === "pending") {
          other.status = "taken";
          other.acceptedById = MY_INSTRUCTOR_ID;
        }
      }
      pushEvent(
        "cover",
        `${DEMO_INSTRUCTORS.i1.name} aceitou a cobertura e assumiu a sessão (primeiro aceite).`,
        DEMO_INSTRUCTORS.i1.name,
        invite.sessionId,
      );
      return { outcome: "accepted", invite: toCoverInvite(invite) };
    },
  },

  coordination: {
    async getCycle(weekStart, signal): Promise<WeeklyCycle> {
      await gate({ role: "coordinator", signal });
      assertValidWeek(weekStart);
      const current = store();
      const offset = weekOffset(weekStart);
      const monday = current.mondayOfThisWeek;
      const records = sessionsOfWeek(weekStart);
      const active = records.filter((record) => derivedStatus(record) !== "cancelled");
      const range = weekRange(weekStart);
      const inWeek = (sessionId: string) => {
        const time = new Date(sessionOrThrow(sessionId).startsAt).getTime();
        return time >= range.start && time < range.end;
      };
      const at = (week: number, day: number, hour: number) =>
        new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + week * 7 + day, hour).toISOString();

      return {
        weekStart,
        weekEnd: weekDays(weekStart)[6],
        phase:
          offset < 0
            ? "closed"
            : offset === 0
              ? "in_progress"
              : offset === 1
                ? "enrollment_open"
                : "collecting_availability",
        availabilityDeadline: offset >= 2 ? at(offset - 1, 2, 18) : null,
        enrollmentOpensAt: at(offset - 1, 4, 8),
        totals: {
          sessions: records.length,
          capacity: records.length ? active.reduce((sum, record) => sum + record.capacity, 0) : null,
          confirmed: records.length ? active.reduce((sum, record) => sum + record.confirmedCount, 0) : null,
          waitlisted: records.length ? active.reduce((sum, record) => sum + record.waitlistCount, 0) : null,
          uncovered: records.filter((record) => derivedStatus(record) === "uncovered").length,
          openCoverRequests: current.coverRequests.filter(
            (request) => request.status === "open" && inWeek(request.sessionId),
          ).length,
          pendingReallocations: current.reallocations.filter(
            (item) => item.status === "pending" && inWeek(item.originSessionId),
          ).length,
        },
        instructors: ALL_INSTRUCTORS.map((instructor) => {
          const record = availabilityRecord(weekStart, instructor.id);
          return {
            instructor,
            status: record.status,
            submittedAt: record.submittedAt,
            sessionsOffered:
              record.selectedSlotIds.length ||
              records.filter((session) => session.instructorId === instructor.id).length,
          };
        }),
      };
    },
    async listSessions(weekStart, signal) {
      await gate({ role: "coordinator", signal });
      assertValidWeek(weekStart);
      const records = sessionsOfWeek(weekStart);
      return {
        weekStart,
        weekEnd: weekDays(weekStart)[6],
        sessions: records.map(toSession),
        published: records.length > 0,
      };
    },
    async roster(sessionId, signal) {
      await gate({ role: "coordinator", signal });
      return buildRoster(sessionOrThrow(sessionId));
    },
    async listCoverRequests(signal) {
      await gate({ role: "coordinator", signal });
      return store()
        .coverRequests.slice()
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        .map(toCoverRequest);
    },
    async listReallocations(signal) {
      await gate({ role: "coordinator", signal });
      return store()
        .reallocations.slice()
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        .map(toReallocation);
    },
    async applyReallocation(id, input) {
      await gate({ role: "coordinator" });
      const record = store().reallocations.find((item) => item.id === id);
      if (!record) fail("not_found", "Reorganização não encontrada.", 404);
      if (record.status !== "pending") {
        fail("conflict", "Esta reorganização já foi tratada.", 409);
      }
      if (input.alternative === "future_priority") {
        record.status = "applied";
        record.alternative = "future_priority";
        record.priorityGrantedAt = new Date().toISOString();
        pushEvent(
          "reallocation",
          "Prioridade futura registrada; sem garantia automática de vaga.",
          DEMO_USERS.coordinator.name,
        );
        return toReallocation(record);
      }
      if (!input.targetSessionId) {
        fail("validation", "Informe a sessão de destino.", 422);
      }
      if (!record.candidateSessionIds.includes(input.targetSessionId)) {
        fail("validation", "A sessão escolhida não é uma opção válida.", 422);
      }
      const target = sessionOrThrow(input.targetSessionId);
      const free = target.capacity - target.confirmedCount;
      if (free < record.participantCount) {
        fail(
          "conflict",
          `A sessão escolhida tem ${plural(free, "vaga")} para ${plural(record.participantCount, "participante")}.`,
          409,
          "not_enough_capacity",
        );
      }
      target.confirmedCount += record.participantCount;
      record.status = "applied";
      record.alternative = "extra_session";
      record.appliedToId = target.id;
      pushEvent(
        "reallocation",
        `${plural(record.participantCount, "participante reorganizado", "participantes reorganizados")} para outra sessão.`,
        DEMO_USERS.coordinator.name,
        target.id,
      );
      return toReallocation(record);
    },
    async dismissReallocation(id) {
      await gate({ role: "coordinator" });
      const record = store().reallocations.find((item) => item.id === id);
      if (!record) fail("not_found", "Reorganização não encontrada.", 404);
      if (record.status !== "pending") {
        fail("conflict", "Esta reorganização já foi tratada.", 409);
      }
      record.status = "dismissed";
      pushEvent("reallocation", "Reorganização dispensada pela coordenação.", DEMO_USERS.coordinator.name);
      return toReallocation(record);
    },
    async listEvents(signal) {
      await gate({ role: "coordinator", signal });
      return store().events.slice();
    },
  },
};
