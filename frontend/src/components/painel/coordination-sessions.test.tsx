import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Session, WeekSessions } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  resource: {
    data: null as WeekSessions | null,
    error: null,
    loading: false,
    refreshing: false,
    reload: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => ({
  api: {
    coordination: {
      listSessions: vi.fn(),
    },
  },
}));

vi.mock("@/lib/hooks/use-account-resource", () => ({
  useAccountResource: () => mocks.resource,
}));

vi.mock("./week-switcher", () => ({
  useWeekSelection: () => ({ current: "2026-11-02", week: "2026-11-02" }),
  WeekSwitcher: () => null,
}));

vi.mock("./instructor-sessions", () => ({
  RosterDialog: () => null,
}));

import { CoordinationSessions } from "./coordination-sessions";

function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    id: "session-1",
    startsAt: "2026-11-03T10:00:00-03:00",
    endsAt: "2026-11-03T11:00:00-03:00",
    location: { id: "loc-1", name: "Sala Principal" },
    instructor: { id: "instructor-1", name: "Ana" },
    capacity: 12,
    confirmedCount: 5,
    waitlistCount: 0,
    status: "scheduled",
    isExtra: false,
    ...overrides,
  };
}

function weekWith(sessions: Session[], published: boolean): WeekSessions {
  return {
    weekStart: "2026-11-02",
    weekEnd: "2026-11-08",
    sessions,
    published,
  };
}

describe("CoordinationSessions", () => {
  beforeEach(() => {
    mocks.resource.data = null;
  });

  it("mostra as sessões existentes mesmo quando published é false", () => {
    mocks.resource.data = weekWith([makeSession()], false);

    render(<CoordinationSessions />);

    expect(screen.queryByText("Nenhuma sessão cadastrada")).not.toBeInTheDocument();
    expect(screen.getByText(/Sala Principal/)).toBeInTheDocument();
    expect(screen.getByText("Abre em breve")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inscrições" })).toBeInTheDocument();
  });

  it("mostra o estado vazio quando não há sessões cadastradas, sem culpar a publicação", () => {
    mocks.resource.data = weekWith([], false);

    render(<CoordinationSessions />);

    expect(screen.getByRole("heading", { name: "Nenhuma sessão cadastrada" })).toBeInTheDocument();
    expect(screen.getByText("Não há sessões cadastradas para esta semana.")).toBeInTheDocument();
    expect(screen.queryByText(/não foi publicada/i)).not.toBeInTheDocument();
  });

  it("mantém o filtro de sessões extras", () => {
    mocks.resource.data = weekWith(
      [
        makeSession({ id: "regular", location: { id: "loc-regular", name: "Sala Regular" } }),
        makeSession({
          id: "extra",
          location: { id: "loc-extra", name: "Sala Extra" },
          isExtra: true,
          status: "open",
        }),
      ],
      true,
    );

    render(<CoordinationSessions />);

    expect(screen.getByText(/Sala Regular/)).toBeInTheDocument();
    expect(screen.getByText(/Sala Extra/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /Somente sessões extras/ }));

    expect(screen.queryByText(/Sala Regular/)).not.toBeInTheDocument();
    expect(screen.getByText(/Sala Extra/)).toBeInTheDocument();
  });

  it("mantém o filtro de sessões que exigem atenção", () => {
    mocks.resource.data = weekWith(
      [
        makeSession({ id: "scheduled", location: { id: "loc-scheduled", name: "Sala Agendada" } }),
        makeSession({
          id: "cancelled",
          location: { id: "loc-cancelled", name: "Sala Cancelada" },
          status: "cancelled",
        }),
      ],
      true,
    );

    render(<CoordinationSessions />);

    expect(screen.getByText(/Sala Agendada/)).toBeInTheDocument();
    expect(screen.getByText(/Sala Cancelada/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /Somente sessões que exigem atenção/ }));

    expect(screen.queryByText(/Sala Agendada/)).not.toBeInTheDocument();
    expect(screen.getByText(/Sala Cancelada/)).toBeInTheDocument();
  });

  it("mostra o estado de filtros sem resultado quando os filtros ocultam todas as sessões", () => {
    mocks.resource.data = weekWith([makeSession()], true);

    render(<CoordinationSessions />);

    fireEvent.click(screen.getByRole("checkbox", { name: /Somente sessões extras/ }));

    expect(screen.getByRole("heading", { name: "Nenhuma sessão corresponde aos filtros" })).toBeInTheDocument();
  });
});
