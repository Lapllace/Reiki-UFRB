import type {
  AcceptCoverResult,
  AppNotification,
  ApplyReallocationInput,
  AuditEvent,
  CoverInvite,
  CoverRequest,
  Enrollment,
  EnrollmentResult,
  InstructorSession,
  Location,
  LoginInput,
  PublishAvailabilityInput,
  Reallocation,
  RosterEntry,
  User,
  WeekSessions,
  WeeklyAvailability,
  WeeklyCycle,
} from "@/lib/types";

/**
 * Interface única da API consumida pela interface.
 * É implementada por `createRealApi` (HTTP) e, apenas em desenvolvimento, pela
 * demonstração em `src/lib/demo`. Isso garante que as telas não saibam de onde
 * os dados vêm.
 */
export interface ReikiApi {
  auth: {
    /** Retorna `null` quando não há sessão ativa. */
    me(signal?: AbortSignal): Promise<User | null>;
    login(input: LoginInput): Promise<User>;
    logout(): Promise<void>;
  };
  locations: {
    list(signal?: AbortSignal): Promise<Location[]>;
  };
  sessions: {
    listWeek(weekStart: string, signal?: AbortSignal): Promise<WeekSessions>;
  };
  enrollments: {
    /** O resultado (confirmada ou fila) é decidido pelo servidor. */
    create(sessionId: string): Promise<EnrollmentResult>;
    listMine(signal?: AbortSignal): Promise<Enrollment[]>;
    cancel(enrollmentId: string): Promise<Enrollment>;
  };
  notifications: {
    list(signal?: AbortSignal): Promise<AppNotification[]>;
    markRead(id: string): Promise<void>;
  };
  availability: {
    /** `weekStart = null`: o servidor devolve a semana atualmente aberta para registro. */
    get(weekStart: string | null, signal?: AbortSignal): Promise<WeeklyAvailability>;
    publish(input: PublishAvailabilityInput): Promise<WeeklyAvailability>;
  };
  instructor: {
    listSessions(signal?: AbortSignal): Promise<InstructorSession[]>;
    roster(sessionId: string, signal?: AbortSignal): Promise<RosterEntry[]>;
    cancelSession(sessionId: string, reason: string): Promise<InstructorSession>;
    listCoverInvites(signal?: AbortSignal): Promise<CoverInvite[]>;
    /** O primeiro aceite registrado pelo servidor assume a sessão. */
    acceptCover(inviteId: string): Promise<AcceptCoverResult>;
  };
  coordination: {
    getCycle(weekStart: string, signal?: AbortSignal): Promise<WeeklyCycle>;
    listSessions(weekStart: string, signal?: AbortSignal): Promise<WeekSessions>;
    roster(sessionId: string, signal?: AbortSignal): Promise<RosterEntry[]>;
    listCoverRequests(signal?: AbortSignal): Promise<CoverRequest[]>;
    listReallocations(signal?: AbortSignal): Promise<Reallocation[]>;
    applyReallocation(id: string, input: ApplyReallocationInput): Promise<Reallocation>;
    dismissReallocation(id: string): Promise<Reallocation>;
    listEvents(signal?: AbortSignal): Promise<AuditEvent[]>;
  };
}
