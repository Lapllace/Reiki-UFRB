import { apiRequest } from "./client";
import type { ReikiApi } from "./contract";
import { endpoints } from "./endpoints";
import { ApiError } from "./errors";
import type {
  AcceptCoverResult,
  AppNotification,
  AuditEvent,
  CoverInvite,
  CoverRequest,
  Enrollment,
  EnrollmentResult,
  CancelSessionResult,
  InstructorSession,
  Location,
  Reallocation,
  RosterEntry,
  User,
  WeekSessions,
  WeeklyAvailability,
  WeeklyCycle,
} from "@/lib/types";

/** Implementação HTTP real dos contratos FastAPI usados pela interface. */
export function createRealApi(): ReikiApi {
  return {
    auth: {
      async me(signal) {
        try {
          return await apiRequest<User>(endpoints.auth.me, { signal });
        } catch (error) {
          // 401 significa apenas "sem sessão": não é uma falha.
          if (error instanceof ApiError && error.kind === "unauthenticated") return null;
          throw error;
        }
      },
      login: (input) => apiRequest<User>(endpoints.auth.login, { method: "POST", body: input }),
      logout: () => apiRequest<void>(endpoints.auth.logout, { method: "POST" }),
    },
    locations: {
      list: (signal) => apiRequest<Location[]>(endpoints.locations, { signal }),
    },
    sessions: {
      listWeek: (weekStart, signal) =>
        apiRequest<WeekSessions>(endpoints.sessions.week, {
          query: { weekStart },
          signal,
        }),
    },
    enrollments: {
      create: (sessionId) =>
        apiRequest<EnrollmentResult>(endpoints.enrollments.create, {
          method: "POST",
          body: { sessionId },
        }),
      listMine: (signal) => apiRequest<Enrollment[]>(endpoints.enrollments.mine, { signal }),
      cancel: (id) =>
        apiRequest<Enrollment>(endpoints.enrollments.cancel(id), { method: "POST" }),
    },
    notifications: {
      list: (signal) => apiRequest<AppNotification[]>(endpoints.notifications.list, { signal }),
      markRead: (id) =>
        apiRequest<void>(endpoints.notifications.markRead(id), { method: "POST" }),
    },
    availability: {
      get: (weekStart, signal) =>
        apiRequest<WeeklyAvailability>(endpoints.instructor.availability, {
          query: { weekStart },
          signal,
        }),
      publish: (input) =>
        apiRequest<WeeklyAvailability>(endpoints.instructor.availability, {
          method: "POST",
          body: {
            week_start: input.weekStart,
            unavailable: input.unavailable,
            note: input.note,
            entries: input.entries.map((entry) => ({
              starts_at: entry.startsAt,
              ends_at: entry.endsAt,
              location_id: entry.locationId,
              note: entry.note,
            })),
          },
        }),
    },
    instructor: {
      listSessions: (signal) =>
        apiRequest<InstructorSession[]>(endpoints.instructor.sessions, { signal }),
      roster: (sessionId, signal) =>
        apiRequest<RosterEntry[]>(endpoints.instructor.roster(sessionId), { signal }),
      cancelSession: (sessionId, reason) =>
        apiRequest<CancelSessionResult>(endpoints.instructor.cancelSession(sessionId), {
          method: "POST",
          body: { reason },
        }),
      listCoverInvites: (signal) =>
        apiRequest<CoverInvite[]>(endpoints.instructor.coverInvites, { signal }),
      acceptCover: async (inviteId) => {
        try {
          return await apiRequest<AcceptCoverResult>(endpoints.instructor.acceptCover(inviteId), {
            method: "POST",
          });
        } catch (error) {
          // Se o contrato final usar 409 para "outro ministrante aceitou primeiro",
          // a tela precisa dos dados atualizados do convite no corpo do erro.
          if (error instanceof ApiError && error.kind === "conflict") {
            const body = error.details as Partial<AcceptCoverResult> | null;
            if (body?.invite && body.outcome) return body as AcceptCoverResult;
          }
          throw error;
        }
      },
    },
    coordination: {
      getCycle: (weekStart, signal) =>
        apiRequest<WeeklyCycle>(endpoints.coordination.cycle(weekStart), { signal }),
      listSessions: (weekStart, signal) =>
        apiRequest<WeekSessions>(endpoints.coordination.sessions, {
          query: { weekStart },
          signal,
        }),
      roster: (sessionId, signal) =>
        apiRequest<RosterEntry[]>(endpoints.coordination.roster(sessionId), { signal }),
      listCoverRequests: (signal) =>
        apiRequest<CoverRequest[]>(endpoints.coordination.coverRequests, { signal }),
      listReallocations: (signal) =>
        apiRequest<Reallocation[]>(endpoints.coordination.reallocations, { signal }),
      applyReallocation: (id, input) =>
        apiRequest<Reallocation>(endpoints.coordination.applyReallocation(id), {
          method: "POST",
          body: input,
        }),
      dismissReallocation: (id) =>
        apiRequest<Reallocation>(endpoints.coordination.dismissReallocation(id), {
          method: "POST",
        }),
      listEvents: (signal) => apiRequest<AuditEvent[]>(endpoints.coordination.events, { signal }),
    },
  };
}
