/**
 * DEMONSTRAÇÃO — dados FICTÍCIOS mantidos apenas em memória do navegador.
 *
 * Nada aqui representa agendamentos, pessoas ou locais reais, e nada é
 * persistido (recarregar a página reinicia o cenário). Este módulo só é
 * carregado quando IS_DEMO é verdadeiro (somente em desenvolvimento).
 */
import { addDays, startOfWeek, toISODate } from "@/lib/dates";
import type {
  AuditEvent,
  CoverInvite,
  CoverRequest,
  EnrollmentStatus,
  InstructorSummary,
  Location,
  NotificationKind,
  AppNotification,
  Reallocation,
  AvailabilityStatus,
  SessionNotice,
  SessionStatus,
  User,
} from "@/lib/types";

export const DEMO_LOCATIONS: Location[] = [
  {
    id: "loc-a",
    name: "Sala Girassol",
    address: "Rua Fictícia, 100 — endereço de demonstração",
    reference: "Ao lado do jardim central (referência fictícia).",
    mapUrl: null,
    notes: "Dado fictício de demonstração.",
  },
  {
    id: "loc-b",
    name: "Espaço Ipê",
    address: "Avenida Imaginária, 250 — endereço de demonstração",
    reference: "Segundo andar, porta azul (referência fictícia).",
    mapUrl: "https://www.openstreetmap.org/",
    notes: "Dado fictício de demonstração. O link de mapa é genérico.",
  },
];

export const DEMO_INSTRUCTORS: Record<"i1" | "i2" | "i3", InstructorSummary> = {
  i1: { id: "ins-1", name: "Helena Duarte" },
  i2: { id: "ins-2", name: "Rafael Moura" },
  i3: { id: "ins-3", name: "Clara Teixeira" },
};

export const DEMO_USERS: Record<"participant" | "instructor" | "coordinator", User> = {
  participant: {
    id: "usr-participant",
    name: "Ana Beatriz Souza",
    email: "ana.demo@exemplo.invalid",
    role: "participant",
  },
  instructor: {
    id: DEMO_INSTRUCTORS.i1.id,
    name: DEMO_INSTRUCTORS.i1.name,
    email: "helena.demo@exemplo.invalid",
    role: "instructor",
  },
  coordinator: {
    id: "usr-coordinator",
    name: "Paulo Henrique Lima",
    email: "paulo.demo@exemplo.invalid",
    role: "coordinator",
  },
};

export const DEMO_PARTICIPANT_NAMES = [
  "Beatriz Almeida",
  "Caio Ferreira",
  "Daniela Rocha",
  "Eduardo Nunes",
  "Fernanda Castro",
  "Gabriel Pires",
  "Isabela Martins",
  "João Vitor Reis",
  "Larissa Gomes",
  "Mateus Cardoso",
  "Natália Barros",
  "Otávio Freitas",
  "Priscila Araújo",
  "Rodrigo Teles",
];

export interface SessionRecord {
  id: string;
  startsAt: string;
  endsAt: string;
  locationId: string;
  instructorId: string | null;
  capacity: number;
  confirmedCount: number;
  waitlistCount: number;
  status: SessionStatus;
  isExtra: boolean;
  notices: SessionNotice[];
  enrollmentOpensAt: string | null;
}

export interface EnrollmentRecord {
  id: string;
  sessionId: string;
  status: EnrollmentStatus;
  waitlistPosition: number | null;
  createdAt: string;
  cancelledAt: string | null;
}

export interface InviteRecord {
  id: string;
  sessionId: string;
  status: CoverInvite["status"];
  createdAt: string;
  acceptedById: string | null;
  /** Se verdadeiro, a demonstração simula outro ministrante aceitando primeiro. */
  simulateLostRace: boolean;
}

export interface CoverRequestRecord extends Omit<CoverRequest, "session"> {
  sessionId: string;
}

export interface ReallocationRecord
  extends Omit<Reallocation, "originSession" | "candidateSessions" | "appliedTo"> {
  originSessionId: string;
  candidateSessionIds: string[];
  appliedToId: string | null;
}

export interface AvailabilityRecord {
  status: AvailabilityStatus;
  submittedAt: string | null;
  selectedSlotIds: string[];
}

export interface DemoState {
  now: Date;
  mondayOfThisWeek: Date;
  sessions: Map<string, SessionRecord>;
  enrollments: Map<string, EnrollmentRecord>;
  notifications: AppNotification[];
  invites: Map<string, InviteRecord>;
  coverRequests: CoverRequestRecord[];
  reallocations: ReallocationRecord[];
  events: AuditEvent[];
  /** weekStart -> instructorId -> registro */
  availability: Map<string, Map<string, AvailabilityRecord>>;
  counters: { enrollment: number; event: number };
}

interface SessionSpec {
  key: string;
  week: number;
  day: number;
  hour: number;
  minute?: number;
  duration?: number;
  loc: "loc-a" | "loc-b";
  ins: "i1" | "i2" | "i3" | null;
  cap: number;
  conf: number;
  wait?: number;
  status?: SessionStatus;
  extra?: boolean;
  notices?: SessionNotice[];
}

function at(monday: Date, week: number, day: number, hour: number, minute = 0): Date {
  return new Date(
    monday.getFullYear(),
    monday.getMonth(),
    monday.getDate() + week * 7 + day,
    hour,
    minute,
  );
}

export function sessionId(week: number, key: string): string {
  return `s-w${week >= 0 ? "p" : "m"}${Math.abs(week)}-${key}`;
}

export const OPEN_AVAILABILITY_WEEK_OFFSET = 2;
export const AVAILABILITY_TEMPLATES: { day: number; hour: number; loc: "loc-a" | "loc-b" }[] = [
  { day: 0, hour: 14, loc: "loc-a" },
  { day: 0, hour: 16, loc: "loc-b" },
  { day: 1, hour: 9, loc: "loc-a" },
  { day: 1, hour: 15, loc: "loc-b" },
  { day: 2, hour: 10, loc: "loc-b" },
  { day: 2, hour: 15, loc: "loc-a" },
  { day: 3, hour: 9, loc: "loc-b" },
  { day: 4, hour: 14, loc: "loc-b" },
  { day: 4, hour: 15, loc: "loc-a" },
  { day: 5, hour: 9, loc: "loc-a" },
];

export function createDemoState(): DemoState {
  const now = new Date();
  const monday = startOfWeek(now);
  const iso = (date: Date) => date.toISOString();

  const specs: SessionSpec[] = [
    // Semana anterior (concluídas)
    { key: "mon", week: -1, day: 0, hour: 14, loc: "loc-a", ins: "i1", cap: 8, conf: 7 },
    { key: "wed", week: -1, day: 2, hour: 15, loc: "loc-b", ins: "i2", cap: 6, conf: 5 },
    { key: "fri", week: -1, day: 4, hour: 14, loc: "loc-a", ins: "i3", cap: 8, conf: 4 },
    // Semana atual
    { key: "mon", week: 0, day: 0, hour: 14, loc: "loc-a", ins: "i1", cap: 8, conf: 5 },
    { key: "tue", week: 0, day: 1, hour: 10, loc: "loc-b", ins: "i2", cap: 6, conf: 4 },
    { key: "wed", week: 0, day: 2, hour: 15, loc: "loc-a", ins: "i1", cap: 8, conf: 6 },
    {
      key: "thu-am",
      week: 0,
      day: 3,
      hour: 9,
      loc: "loc-b",
      ins: "i2",
      cap: 6,
      conf: 6,
      wait: 2,
      status: "full",
    },
    {
      key: "thu-pm",
      week: 0,
      day: 3,
      hour: 16,
      loc: "loc-a",
      ins: "i3",
      cap: 8,
      conf: 4,
      status: "cancelled",
      notices: [
        {
          kind: "cancelled",
          message:
            "Sessão cancelada pelo ministrante. Nenhum substituto assumiu; os participantes serão reorganizados.",
        },
      ],
    },
    {
      key: "fri",
      week: 0,
      day: 4,
      hour: 14,
      loc: "loc-b",
      ins: "i2",
      cap: 8,
      conf: 3,
      notices: [
        {
          kind: "instructor_changed",
          message: "Ministrante alterado: Rafael Moura assume no lugar de Clara Teixeira.",
        },
      ],
    },
    {
      key: "sat-extra",
      week: 0,
      day: 5,
      hour: 9,
      loc: "loc-a",
      ins: "i1",
      cap: 10,
      conf: 2,
      extra: true,
      notices: [{ kind: "info", message: "Sessão extra aberta para reorganização de participantes." }],
    },
    // Próxima semana (inscrições abertas)
    { key: "mon", week: 1, day: 0, hour: 14, loc: "loc-a", ins: "i1", cap: 8, conf: 3 },
    {
      key: "tue",
      week: 1,
      day: 1,
      hour: 15,
      loc: "loc-b",
      ins: "i2",
      cap: 4,
      conf: 4,
      wait: 3,
      status: "full",
    },
    {
      key: "wed",
      week: 1,
      day: 2,
      hour: 10,
      loc: "loc-b",
      ins: null,
      cap: 6,
      conf: 2,
      status: "uncovered",
      notices: [
        {
          kind: "needs_cover",
          message: "Sem ministrante no momento. Nenhum substituto assumiu até agora.",
        },
      ],
    },
    { key: "thu", week: 1, day: 3, hour: 9, loc: "loc-b", ins: "i3", cap: 6, conf: 0 },
    {
      key: "fri",
      week: 1,
      day: 4,
      hour: 15,
      loc: "loc-a",
      ins: null,
      cap: 8,
      conf: 5,
      status: "needs_cover",
      notices: [
        {
          kind: "needs_cover",
          message: "O ministrante cancelou. Procuramos um substituto; sua vaga está mantida por enquanto.",
        },
      ],
    },
    {
      key: "sat",
      week: 1,
      day: 5,
      hour: 10,
      loc: "loc-b",
      ins: null,
      cap: 6,
      conf: 1,
      status: "needs_cover",
      notices: [{ kind: "needs_cover", message: "Aguardando um ministrante para cobrir esta sessão." }],
    },
  ];

  const sessions = new Map<string, SessionRecord>();
  for (const spec of specs) {
    const start = at(monday, spec.week, spec.day, spec.hour, spec.minute ?? 0);
    const end = new Date(start.getTime() + (spec.duration ?? 60) * 60_000);
    const id = sessionId(spec.week, spec.key);
    sessions.set(id, {
      id,
      startsAt: iso(start),
      endsAt: iso(end),
      locationId: spec.loc,
      instructorId: spec.ins ? DEMO_INSTRUCTORS[spec.ins].id : null,
      capacity: spec.cap,
      confirmedCount: spec.conf,
      waitlistCount: spec.wait ?? 0,
      status: spec.status ?? "open",
      isExtra: spec.extra ?? false,
      notices: spec.notices ?? [],
      enrollmentOpensAt: null,
    });
  }

  const enrollments = new Map<string, EnrollmentRecord>();
  const addEnrollment = (
    id: string,
    sid: string,
    status: EnrollmentStatus,
    createdDaysAgo: number,
    waitlistPosition: number | null = null,
    cancelled = false,
  ) => {
    enrollments.set(id, {
      id,
      sessionId: sid,
      status,
      waitlistPosition,
      createdAt: iso(addDays(now, -createdDaysAgo)),
      cancelledAt: cancelled ? iso(addDays(now, -createdDaysAgo + 1)) : null,
    });
  };
  addEnrollment("enr-1", sessionId(-1, "mon"), "confirmed", 9);
  addEnrollment("enr-2", sessionId(-1, "fri"), "confirmed", 8);
  addEnrollment("enr-3", sessionId(-1, "wed"), "cancelled", 8, null, true);
  addEnrollment("enr-4", sessionId(0, "wed"), "confirmed", 5);
  addEnrollment("enr-5", sessionId(0, "thu-pm"), "cancelled", 4, null, true);
  addEnrollment("enr-6", sessionId(1, "mon"), "confirmed", 2);
  addEnrollment("enr-7", sessionId(1, "tue"), "waitlisted", 1, 2);
  addEnrollment("enr-8", sessionId(1, "fri"), "confirmed", 1);

  const notification = (
    id: string,
    kind: NotificationKind,
    title: string,
    message: string,
    hoursAgo: number,
    read: boolean,
    sid?: string,
  ): AppNotification => ({
    id,
    kind,
    title,
    message,
    createdAt: iso(new Date(now.getTime() - hoursAgo * 3_600_000)),
    read,
    sessionId: sid ?? null,
  });

  const notifications: AppNotification[] = [
    notification(
      "n-1",
      "session_cancelled",
      "Sessão de quinta-feira cancelada",
      "A sessão de quinta-feira, às 16:00, na Sala Girassol foi cancelada. Sua inscrição foi encerrada.",
      5,
      false,
      sessionId(0, "thu-pm"),
    ),
    notification(
      "n-2",
      "reallocation",
      "Reorganização em andamento",
      "A coordenação está avaliando uma sessão extra ou uma semana futura para os participantes afetados. Você será avisado(a) assim que houver uma definição.",
      4,
      false,
    ),
    notification(
      "n-3",
      "session_cancelled",
      "Ministrante procura substituto na sexta-feira (semana seguinte)",
      "O ministrante da sessão de sexta-feira, às 15:00, cancelou. Sua vaga foi mantida enquanto buscamos um substituto.",
      20,
      false,
      sessionId(1, "fri"),
    ),
    notification(
      "n-4",
      "extra_session",
      "Nova sessão extra no sábado",
      "Uma sessão extra foi aberta no sábado, às 09:00, na Sala Girassol.",
      30,
      true,
      sessionId(0, "sat-extra"),
    ),
    notification(
      "n-5",
      "instructor_changed",
      "Mudança de ministrante",
      "Na sessão de sexta-feira, às 14:00, Rafael Moura assume no lugar de Clara Teixeira.",
      52,
      true,
      sessionId(0, "fri"),
    ),
  ];

  const invites = new Map<string, InviteRecord>();
  const addInvite = (
    id: string,
    sid: string,
    status: CoverInvite["status"],
    hoursAgo: number,
    acceptedById: string | null = null,
    simulateLostRace = false,
  ) => {
    invites.set(id, {
      id,
      sessionId: sid,
      status,
      createdAt: iso(new Date(now.getTime() - hoursAgo * 3_600_000)),
      acceptedById,
      simulateLostRace,
    });
  };
  addInvite("ci-1", sessionId(1, "fri"), "pending", 20);
  addInvite("ci-2", sessionId(1, "sat"), "pending", 3, null, true);
  addInvite("ci-3", sessionId(0, "fri"), "taken", 90, DEMO_INSTRUCTORS.i2.id);
  addInvite("ci-4", sessionId(-1, "fri"), "accepted", 200, DEMO_INSTRUCTORS.i1.id);

  const session = (week: number, key: string) => sessions.get(sessionId(week, key))!;

  const coverRequests: CoverRequestRecord[] = [
    {
      id: "cr-1",
      status: "open",
      sessionId: sessionId(1, "fri"),
      originalInstructor: DEMO_INSTRUCTORS.i2,
      reason: "Compromisso inesperado.",
      invitedCount: 3,
      createdAt: invites.get("ci-1")!.createdAt,
    },
    {
      id: "cr-2",
      status: "open",
      sessionId: sessionId(1, "sat"),
      originalInstructor: DEMO_INSTRUCTORS.i3,
      reason: null,
      invitedCount: 3,
      createdAt: invites.get("ci-2")!.createdAt,
    },
    {
      id: "cr-3",
      status: "uncovered",
      sessionId: sessionId(1, "wed"),
      originalInstructor: DEMO_INSTRUCTORS.i3,
      reason: "Indisponibilidade de saúde.",
      invitedCount: 3,
      createdAt: iso(new Date(now.getTime() - 60 * 3_600_000)),
    },
    {
      id: "cr-4",
      status: "covered",
      sessionId: sessionId(0, "fri"),
      originalInstructor: DEMO_INSTRUCTORS.i3,
      reason: "Compromisso acadêmico.",
      invitedCount: 3,
      createdAt: invites.get("ci-3")!.createdAt,
      resolvedAt: iso(new Date(now.getTime() - 88 * 3_600_000)),
      coveredBy: DEMO_INSTRUCTORS.i2,
    },
  ];

  const reallocations: ReallocationRecord[] = [
    {
      id: "ra-1",
      status: "pending",
      reason: "Cancelamento sem substituto (quinta-feira, 16:00).",
      originSessionId: sessionId(0, "thu-pm"),
      participantCount: session(0, "thu-pm").confirmedCount,
      candidateSessionIds: [sessionId(0, "sat-extra"), sessionId(1, "mon"), sessionId(1, "thu")],
      appliedToId: null,
      createdAt: iso(new Date(now.getTime() - 5 * 3_600_000)),
    },
    {
      id: "ra-2",
      status: "pending",
      reason: "Sessão sem ministrante (quarta-feira, 10:00, próxima semana).",
      originSessionId: sessionId(1, "wed"),
      participantCount: session(1, "wed").confirmedCount,
      candidateSessionIds: [sessionId(1, "thu"), sessionId(1, "mon")],
      appliedToId: null,
      createdAt: iso(new Date(now.getTime() - 30 * 3_600_000)),
    },
    {
      id: "ra-3",
      status: "applied",
      reason: "Cancelamento (semana anterior).",
      originSessionId: sessionId(-1, "wed"),
      participantCount: 2,
      candidateSessionIds: [sessionId(0, "tue")],
      appliedToId: sessionId(0, "tue"),
      createdAt: iso(addDays(now, -7)),
    },
  ];

  const event = (
    id: number,
    kind: AuditEvent["kind"],
    hoursAgo: number,
    description: string,
    actor: string | null,
    sid?: string,
  ): AuditEvent => ({
    id: `ev-${id}`,
    kind,
    at: iso(new Date(now.getTime() - hoursAgo * 3_600_000)),
    description,
    actor,
    sessionId: sid ?? null,
  });

  const events: AuditEvent[] = [
    event(1, "cancellation", 5, "Clara Teixeira cancelou a sessão de quinta-feira, 16:00 (Sala Girassol).", "Clara Teixeira", sessionId(0, "thu-pm")),
    event(2, "cover", 5, "Solicitação de cobertura enviada a 3 ministrantes elegíveis.", "Sistema", sessionId(0, "thu-pm")),
    event(3, "reallocation", 4, "Reorganização criada para 4 participantes da sessão cancelada.", "Sistema", sessionId(0, "thu-pm")),
    event(4, "cancellation", 20, "Rafael Moura cancelou a sessão de sexta-feira, 15:00 (semana seguinte).", "Rafael Moura", sessionId(1, "fri")),
    event(5, "extra_session", 30, "Sessão extra criada: sábado, 09:00, Sala Girassol.", "Paulo Henrique Lima", sessionId(0, "sat-extra")),
    event(6, "cover", 60, "Nenhum ministrante aceitou cobrir a quarta-feira, 10:00 (semana seguinte).", "Sistema", sessionId(1, "wed")),
    event(7, "session_change", 88, "Rafael Moura assumiu a sessão de sexta-feira, 14:00 (primeiro aceite).", "Rafael Moura", sessionId(0, "fri")),
    event(8, "availability", 120, "Clara Teixeira declarou indisponibilidade para a semana seguinte.", "Clara Teixeira"),
    event(9, "cycle", 170, "Inscrições da semana atual abertas.", "Sistema"),
    event(10, "cycle", 340, "Disponibilidades da semana anterior encerradas.", "Sistema"),
  ];

  const availability = new Map<string, Map<string, AvailabilityRecord>>();
  const setAvailability = (week: number, row: Record<string, AvailabilityRecord>) => {
    availability.set(toISODate(addDays(monday, week * 7)), new Map(Object.entries(row)));
  };
  const published = (hoursAgo: number): AvailabilityRecord => ({
    status: "published",
    submittedAt: iso(new Date(now.getTime() - hoursAgo * 3_600_000)),
    selectedSlotIds: [],
  });
  const pending: AvailabilityRecord = { status: "pending", submittedAt: null, selectedSlotIds: [] };
  for (const week of [-1, 0, 1]) {
    setAvailability(week, {
      [DEMO_INSTRUCTORS.i1.id]: published(300 - week * 100),
      [DEMO_INSTRUCTORS.i2.id]: published(280 - week * 100),
      [DEMO_INSTRUCTORS.i3.id]: published(260 - week * 100),
    });
  }
  setAvailability(2, {
    [DEMO_INSTRUCTORS.i1.id]: pending,
    [DEMO_INSTRUCTORS.i2.id]: published(10),
    [DEMO_INSTRUCTORS.i3.id]: {
      status: "unavailable",
      submittedAt: iso(new Date(now.getTime() - 120 * 3_600_000)),
      selectedSlotIds: [],
    },
  });

  return {
    now,
    mondayOfThisWeek: monday,
    sessions,
    enrollments,
    notifications,
    invites,
    coverRequests,
    reallocations,
    events,
    availability,
    counters: { enrollment: 100, event: 100 },
  };
}
