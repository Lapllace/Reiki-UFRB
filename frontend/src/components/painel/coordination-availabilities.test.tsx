import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import type {
  CoordinationAvailabilityEntry,
  CoordinationInstructorAvailability,
  WeekAvailabilities,
} from "@/lib/types";

const mocks = vi.hoisted(() => ({
  createCycle: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    coordination: {
      createCycle: mocks.createCycle,
    },
  },
}));

import { CoordinationAvailabilities } from "./coordination-availabilities";

const STALE_TITLE = "Ciclo criado, mas os dados não foram atualizados";

function makeEntry(
  overrides: Partial<CoordinationAvailabilityEntry> = {},
): CoordinationAvailabilityEntry {
  return {
    id: "entry-1",
    kind: "available",
    startsAt: "2026-11-09T14:00:00",
    endsAt: "2026-11-09T15:00:00",
    location: { id: "loc-1", name: "Sala Girassol" },
    note: null,
    isCurrent: true,
    convertedSessionId: null,
    ...overrides,
  };
}

function makeInstructor(
  overrides: Partial<CoordinationInstructorAvailability> = {},
): CoordinationInstructorAvailability {
  return {
    instructorId: "instructor-1",
    availabilityId: "availability-1",
    name: "Helena Duarte",
    status: "submitted",
    submittedAt: "2026-11-03T10:00:00",
    note: null,
    entries: [],
    ...overrides,
  };
}

function makeWeek(overrides: Partial<WeekAvailabilities> = {}): WeekAvailabilities {
  return {
    weekStart: "2026-11-09",
    weekEnd: "2026-11-15",
    cycleId: "cycle-1",
    cyclePhase: "collecting_availability",
    instructors: [],
    ...overrides,
  };
}

function weekWithoutCycle(overrides: Partial<WeekAvailabilities> = {}): WeekAvailabilities {
  return makeWeek({ cycleId: null, cyclePhase: null, instructors: [], ...overrides });
}

function availabilityElement(
  props: Partial<Parameters<typeof CoordinationAvailabilities>[0]> = {},
) {
  return (
    <CoordinationAvailabilities
      week="2026-11-09"
      data={makeWeek()}
      loading={false}
      refreshing={false}
      onRetry={vi.fn()}
      {...props}
    />
  );
}

function renderAvailability(
  props: Partial<Parameters<typeof CoordinationAvailabilities>[0]> = {},
) {
  return render(availabilityElement(props));
}

describe("CoordinationAvailabilities", () => {
  beforeEach(() => {
    mocks.createCycle.mockReset();
  });

  it("mostra situação, ofertas vigentes, histórico e ofertas convertidas", () => {
    const data = makeWeek({
      instructors: [
        makeInstructor({
          note: "Prefiro à tarde",
          entries: [
            makeEntry(),
            makeEntry({
              id: "entry-2",
              startsAt: "2026-11-12T09:00:00",
              endsAt: "2026-11-12T10:00:00",
              location: null,
            }),
            makeEntry({
              id: "entry-history",
              startsAt: "2026-11-10T10:00:00",
              endsAt: "2026-11-10T11:00:00",
              isCurrent: false,
              convertedSessionId: "session-1",
              note: "Oferta anterior substituída.",
            }),
          ],
        }),
        makeInstructor({
          instructorId: "instructor-2",
          availabilityId: null,
          name: "Rafael Moura",
          status: "pending",
          submittedAt: null,
          entries: [],
        }),
        makeInstructor({
          instructorId: "instructor-3",
          name: "Clara Teixeira",
          status: "unavailable",
          entries: [],
        }),
      ],
    });

    renderAvailability({ data });

    expect(
      screen.getByRole("heading", { name: "Disponibilidades dos ministrantes" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Ciclo criado")).toBeInTheDocument();
    expect(screen.getByText("Fase atual: Disponibilidades.")).toBeInTheDocument();
    expect(screen.getByText("Ciclo ativo")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Criar ciclo da semana" }),
    ).not.toBeInTheDocument();

    expect(screen.getByText("Helena Duarte")).toBeInTheDocument();
    expect(screen.getByText("Rafael Moura")).toBeInTheDocument();
    expect(screen.getByText("Clara Teixeira")).toBeInTheDocument();
    expect(screen.getByText("Registrada")).toBeInTheDocument();
    expect(screen.getByText("Pendente")).toBeInTheDocument();
    expect(screen.getByText("Indisponível")).toBeInTheDocument();

    expect(screen.getByText(/Prefiro à tarde/)).toBeInTheDocument();
    expect(screen.getAllByText(/Sala Girassol/)).toHaveLength(2);
    expect(screen.getByText(/Local não informado/)).toBeInTheDocument();
    expect(screen.getByText("Ofertas vigentes")).toBeInTheDocument();
    expect(screen.getByText("Histórico (não vigente)")).toBeInTheDocument();
    expect(screen.getByText("Histórico")).toBeInTheDocument();
    expect(screen.getByText("Convertida em sessão")).toBeInTheDocument();
    expect(screen.getByText(/Oferta anterior substituída\./)).toBeInTheDocument();
    expect(
      screen.getByText("Aguardando o registro de disponibilidade."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Declarou indisponibilidade para esta semana."),
    ).toBeInTheDocument();

    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuemin", "0");
    expect(progress).toHaveAttribute("aria-valuemax", "3");
    expect(progress).toHaveAttribute("aria-valuenow", "2");
    expect(screen.getByText("2 de 3 registraram")).toBeInTheDocument();
  });

  it("só cria o ciclo ao clicar e recarrega os dados após o sucesso", async () => {
    mocks.createCycle.mockResolvedValue({
      id: "cycle-1",
      weekStart: "2026-11-09",
      status: "collecting_availability",
      instructors: [],
    });
    const onRefresh = vi.fn().mockResolvedValue(true);

    renderAvailability({
      data: weekWithoutCycle(),
      onRefresh,
    });

    expect(screen.getByText("Ciclo ainda não criado")).toBeInTheDocument();
    expect(
      screen.getByText(/Nenhum ciclo é criado automaticamente/i),
    ).toBeInTheDocument();
    expect(mocks.createCycle).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Criar ciclo da semana" }));

    await waitFor(() =>
      expect(mocks.createCycle).toHaveBeenCalledWith({ weekStart: "2026-11-09" }),
    );
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Ciclo da semana disponível")).toBeInTheDocument();
    expect(screen.getByText("Ciclo criado")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Criar ciclo da semana" }),
    ).not.toBeInTheDocument();
  });

  it("desabilita o botão de criação enquanto o POST está em andamento", async () => {
    let resolveCreate: (value: unknown) => void = () => {};
    mocks.createCycle.mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );
    const onRefresh = vi.fn().mockResolvedValue(true);

    renderAvailability({ data: weekWithoutCycle(), onRefresh });

    const button = screen.getByRole("button", { name: "Criar ciclo da semana" });
    fireEvent.click(button);

    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(mocks.createCycle).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveCreate({
        id: "cycle-1",
        weekStart: "2026-11-09",
        status: "collecting_availability",
        instructors: [],
      });
    });
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
  });

  it("informa que o ciclo foi criado quando a atualização falha", async () => {
    mocks.createCycle.mockResolvedValue({
      id: "cycle-1",
      weekStart: "2026-11-09",
      status: "collecting_availability",
      instructors: [],
    });
    const onRefresh = vi.fn().mockRejectedValue(new Error("servidor indisponível"));

    renderAvailability({ data: weekWithoutCycle(), onRefresh });

    fireEvent.click(screen.getByRole("button", { name: "Criar ciclo da semana" }));

    expect(await screen.findByText(STALE_TITLE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tentar atualizar" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Criar ciclo da semana" }),
    ).not.toBeInTheDocument();
    expect(mocks.createCycle).toHaveBeenCalledTimes(1);
  });

  it("tentar atualizar repete apenas a atualização, sem criar o ciclo novamente", async () => {
    mocks.createCycle.mockResolvedValue({
      id: "cycle-1",
      weekStart: "2026-11-09",
      status: "collecting_availability",
      instructors: [],
    });
    const onRefresh = vi.fn().mockResolvedValue(false);

    renderAvailability({ data: weekWithoutCycle(), onRefresh });

    fireEvent.click(screen.getByRole("button", { name: "Criar ciclo da semana" }));
    await screen.findByText(STALE_TITLE);

    fireEvent.click(screen.getByRole("button", { name: "Tentar atualizar" }));

    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(2));
    expect(mocks.createCycle).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(STALE_TITLE)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Criar ciclo da semana" }),
    ).not.toBeInTheDocument();
  });

  it("sai do estado de recuperação quando a atualização posterior funciona", async () => {
    mocks.createCycle.mockResolvedValue({
      id: "cycle-1",
      weekStart: "2026-11-09",
      status: "collecting_availability",
      instructors: [],
    });
    const onRefresh = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true);

    renderAvailability({ data: weekWithoutCycle(), onRefresh });

    fireEvent.click(screen.getByRole("button", { name: "Criar ciclo da semana" }));
    await screen.findByText(STALE_TITLE);

    fireEvent.click(screen.getByRole("button", { name: "Tentar atualizar" }));

    await waitFor(() => expect(screen.queryByText(STALE_TITLE)).not.toBeInTheDocument());
    expect(screen.getByText("Ciclo criado")).toBeInTheDocument();
    expect(screen.getByText("Ciclo da semana disponível")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Criar ciclo da semana" }),
    ).not.toBeInTheDocument();
    expect(mocks.createCycle).toHaveBeenCalledTimes(1);
  });

  it("mostra o erro da criação e permite tentar novamente", async () => {
    mocks.createCycle.mockRejectedValue(
      new ApiError("conflict", "O ciclo não pôde ser criado agora.", { status: 409 }),
    );

    renderAvailability({
      data: weekWithoutCycle(),
    });

    fireEvent.click(screen.getByRole("button", { name: "Criar ciclo da semana" }));

    expect(
      await screen.findByText("Não foi possível criar o ciclo"),
    ).toBeInTheDocument();
    expect(screen.getByText("O ciclo não pôde ser criado agora.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Criar ciclo da semana" }),
    ).toBeEnabled();
  });

  it("descarta o estado de recuperação ao trocar de semana", async () => {
    mocks.createCycle.mockResolvedValue({
      id: "cycle-1",
      weekStart: "2026-11-09",
      status: "collecting_availability",
      instructors: [],
    });
    const onRefresh = vi.fn().mockResolvedValue(false);

    const { rerender } = renderAvailability({
      data: weekWithoutCycle(),
      onRefresh,
    });

    fireEvent.click(screen.getByRole("button", { name: "Criar ciclo da semana" }));
    await screen.findByText(STALE_TITLE);

    rerender(
      availabilityElement({
        week: "2026-11-16",
        data: weekWithoutCycle({ weekStart: "2026-11-16", weekEnd: "2026-11-22" }),
        onRefresh,
      }),
    );

    expect(screen.queryByText(STALE_TITLE)).not.toBeInTheDocument();
    expect(screen.getByText("Ciclo ainda não criado")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Criar ciclo da semana" }),
    ).toBeEnabled();
  });

  it("ignora a criação concluída depois de trocar de semana", async () => {
    let resolveCreate: (value: unknown) => void = () => {};
    mocks.createCycle.mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );
    const onRefresh = vi.fn().mockResolvedValue(true);

    const { rerender } = renderAvailability({
      data: weekWithoutCycle(),
      onRefresh,
    });

    fireEvent.click(screen.getByRole("button", { name: "Criar ciclo da semana" }));
    await waitFor(() => expect(mocks.createCycle).toHaveBeenCalledTimes(1));

    rerender(
      availabilityElement({
        week: "2026-11-16",
        data: weekWithoutCycle({ weekStart: "2026-11-16", weekEnd: "2026-11-22" }),
        onRefresh,
      }),
    );

    expect(screen.getByText("Ciclo ainda não criado")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Criar ciclo da semana" }),
    ).toBeEnabled();

    await act(async () => {
      resolveCreate({
        id: "cycle-1",
        weekStart: "2026-11-09",
        status: "collecting_availability",
        instructors: [],
      });
    });

    expect(onRefresh).not.toHaveBeenCalled();
    expect(screen.getByText("Ciclo ainda não criado")).toBeInTheDocument();
    expect(screen.queryByText("Ciclo criado")).not.toBeInTheDocument();
  });

  it("anuncia o carregamento sem exibir estado vazio enganoso", () => {
    renderAvailability({ data: undefined, loading: true });

    expect(screen.getByText("Carregando disponibilidades…")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Nenhum ministrante cadastrado" }),
    ).not.toBeInTheDocument();
  });

  it("mostra o erro de consulta e permite tentar novamente", () => {
    const onRetry = vi.fn();
    renderAvailability({
      data: undefined,
      error: new ApiError("network", "Não foi possível carregar as disponibilidades."),
      onRetry,
    });

    expect(screen.getByText("Sem conexão com o servidor")).toBeInTheDocument();
    expect(
      screen.getByText("Não foi possível carregar as disponibilidades."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("indica atualização em segundo plano mantendo os dados visíveis", () => {
    renderAvailability({ data: makeWeek(), refreshing: true });

    expect(screen.getByText("Atualizando disponibilidades…")).toBeInTheDocument();
    expect(screen.getByText("Ciclo criado")).toBeInTheDocument();
  });

  it("mostra o estado vazio quando não há ministrantes", () => {
    renderAvailability({ data: makeWeek({ instructors: [] }) });

    expect(
      screen.getByRole("heading", { name: "Nenhum ministrante cadastrado" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Não há ministrantes ativos para esta semana."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});
