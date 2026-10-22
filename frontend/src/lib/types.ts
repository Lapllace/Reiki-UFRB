/**
 * Tipos de domínio usados pelo frontend.
 *
 * CONTRATO A DEFINIR: o backend (FastAPI + PostgreSQL) ainda não publicou o
 * esquema da API. Estes tipos descrevem o que a interface PRECISA receber para
 * funcionar. Quando o contrato oficial existir, ajuste este arquivo (ou gere os
 * tipos a partir do OpenAPI) e os mapeadores em `src/lib/api/services.ts`.
 *
 * Convenções assumidas:
 *  - datas/horas completas em ISO 8601 com fuso (ex.: "2026-10-26T14:00:00-03:00");
 *  - semanas identificadas pela data do primeiro dia da semana ("YYYY-MM-DD");
 *  - campos opcionais (`?`/`null`) podem não ser fornecidos e a UI deve tolerar isso.
 */

export type Role = "participant" | "instructor" | "coordinator";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export interface Location {
  id: string;
  name: string;
  /** Endereço completo, quando confirmado pela coordenação. */
  address?: string | null;
  /** Ponto de referência / como chegar. */
  reference?: string | null;
  /** Link para mapa (Google Maps, OpenStreetMap etc.). */
  mapUrl?: string | null;
  /** Observações de acesso (acessibilidade, orientações). */
  notes?: string | null;
}

export interface InstructorSummary {
  id: string;
  name: string;
}

/**
 * Estado da sessão segundo o servidor.
 *  - `scheduled`: publicada, mas as inscrições ainda não abriram;
 *  - `open`: inscrições abertas;
 *  - `full`: sem vagas (fila de espera pode estar disponível);
 *  - `cancelled`: cancelada;
 *  - `needs_cover`: ministrante cancelou e há convite de cobertura em andamento;
 *  - `uncovered`: sem substituto até o momento;
 *  - `completed`: já realizada.
 */
export type SessionStatus =
  | "scheduled"
  | "open"
  | "full"
  | "cancelled"
  | "needs_cover"
  | "uncovered"
  | "completed";

export type SessionNoticeKind =
  | "cancelled"
  | "instructor_changed"
  | "reallocation"
  | "needs_cover"
  | "info";

export interface SessionNotice {
  kind: SessionNoticeKind;
  message: string;
}

export type EnrollmentStatus =
  | "confirmed"
  | "waitlisted"
  | "attended"
  | "cancelled";

export interface MyEnrollmentRef {
  id: string;
  status: EnrollmentStatus;
  waitlistPosition?: number | null;
}

export interface Session {
  id: string;
  startsAt: string;
  endsAt: string;
  location: Location;
  /** Pode ser nulo quando a sessão está sem ministrante (cobertura pendente). */
  instructor: InstructorSummary | null;
  /** Nulos quando o backend não informa capacidade/ocupação. */
  capacity: number | null;
  confirmedCount: number | null;
  waitlistCount: number | null;
  /** O servidor informa se a fila de espera está habilitada para a sessão. */
  waitlistEnabled?: boolean;
  status: SessionStatus;
  /** Sessão extra criada fora do ciclo regular. */
  isExtra?: boolean;
  /** Quando as inscrições abrem (para `scheduled`). */
  enrollmentOpensAt?: string | null;
  notices?: SessionNotice[];
  /** Inscrição do usuário autenticado nesta sessão, se houver. */
  myEnrollment?: MyEnrollmentRef | null;
}

export interface Enrollment {
  id: string;
  status: EnrollmentStatus;
  waitlistPosition?: number | null;
  createdAt: string;
  cancelledAt?: string | null;
  session: Session;
  /** Decisão do servidor: permite cancelar? */
  canCancel: boolean;
  /** Explicação exibida quando `canCancel` é falso. */
  cancelBlockedReason?: string | null;
}

export type NotificationKind =
  | "session_cancelled"
  | "instructor_changed"
  | "reallocation"
  | "extra_session"
  | "waitlist_promoted"
  | "info";

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  title: string;
  message: string;
  createdAt: string;
  read: boolean;
  sessionId?: string | null;
}

/* ----------------------------- Ministrante ------------------------------ */

/** Janela (dia + horário + local) oferecida pela coordenação para o ministrante escolher. */
export interface SlotOption {
  id: string;
  /** Início em ISO 8601. */
  startsAt: string;
  endsAt: string;
  location: Location;
}

export type AvailabilityStatus = "pending" | "published" | "unavailable";

export interface WeeklyAvailability {
  weekStart: string;
  weekEnd: string;
  status: AvailabilityStatus;
  /** Prazo para registrar, quando definido. */
  deadline?: string | null;
  /** O servidor informa se o registro está aberto/editável. */
  canEdit: boolean;
  lockedReason?: string | null;
  options: SlotOption[];
  selectedSlotIds: string[];
}

export interface PublishAvailabilityInput {
  weekStart: string;
  /** `true` para declarar indisponibilidade na semana inteira. */
  unavailable: boolean;
  slotIds: string[];
}

export interface RosterEntry {
  enrollmentId: string;
  participantName: string;
  status: EnrollmentStatus;
  waitlistPosition?: number | null;
}

export interface InstructorSession {
  session: Session;
  canCancel: boolean;
  cancelBlockedReason?: string | null;
}

export type CoverInviteStatus =
  | "pending"
  | "accepted"
  | "taken"
  | "expired"
  | "withdrawn";

export interface CoverInvite {
  id: string;
  status: CoverInviteStatus;
  session: Session;
  createdAt: string;
  expiresAt?: string | null;
  /** Quem assumiu a sessão (quando `taken`). */
  acceptedBy?: InstructorSummary | null;
}

/** Resultado da tentativa de aceitar — decidido SEMPRE pelo servidor. */
export interface AcceptCoverResult {
  outcome: "accepted" | "already_taken" | "expired";
  invite: CoverInvite;
}

/* ------------------------------ Coordenação ------------------------------ */

export type CyclePhase =
  | "collecting_availability"
  | "enrollment_pending"
  | "enrollment_open"
  | "in_progress"
  | "closed";

export interface InstructorAvailabilityRow {
  instructor: InstructorSummary;
  status: AvailabilityStatus;
  submittedAt?: string | null;
  sessionsOffered: number;
}

export interface WeeklyCycle {
  weekStart: string;
  weekEnd: string;
  phase: CyclePhase;
  availabilityDeadline?: string | null;
  enrollmentOpensAt?: string | null;
  totals: {
    sessions: number;
    capacity: number | null;
    confirmed: number | null;
    waitlisted: number | null;
    uncovered: number;
    openCoverRequests: number;
    pendingReallocations: number;
  };
  instructors: InstructorAvailabilityRow[];
}

export interface CoordinatorSession {
  session: Session;
}

export type CoverRequestStatus = "open" | "covered" | "uncovered";

export interface CoverRequest {
  id: string;
  status: CoverRequestStatus;
  session: Session;
  originalInstructor: InstructorSummary | null;
  reason?: string | null;
  invitedCount: number;
  createdAt: string;
  resolvedAt?: string | null;
  coveredBy?: InstructorSummary | null;
}

export type ReallocationStatus = "pending" | "applied" | "dismissed";

export interface Reallocation {
  id: string;
  status: ReallocationStatus;
  reason: string;
  originSession: Session;
  participantCount: number;
  /** Sessões candidatas (extras ou de semanas futuras) sugeridas pelo servidor. */
  candidateSessions: Session[];
  appliedTo?: Session | null;
  createdAt: string;
}

export interface ApplyReallocationInput {
  targetSessionId: string;
}

export type AuditEventKind =
  | "cycle"
  | "availability"
  | "cover"
  | "cancellation"
  | "extra_session"
  | "reallocation"
  | "session_change";

export interface AuditEvent {
  id: string;
  kind: AuditEventKind;
  at: string;
  actor?: string | null;
  description: string;
  sessionId?: string | null;
}

/* --------------------------------- Comuns -------------------------------- */

export interface LoginInput {
  email: string;
  password: string;
}

export interface EnrollmentResult {
  enrollment: Enrollment;
}

export interface WeekSessions {
  weekStart: string;
  weekEnd: string;
  sessions: Session[];
  /** `false` quando a semana ainda não foi publicada pela coordenação. */
  published: boolean;
}
