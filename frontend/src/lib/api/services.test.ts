import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CycleManagement, WeekAvailabilities } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("./client", () => ({
  apiRequest: mocks.apiRequest,
}));

import { createRealApi } from "./services";

const cycle: CycleManagement = {
  id: "cycle-1",
  weekStart: "2026-11-09",
  status: "collecting_availability",
  instructors: [],
};

const availabilities: WeekAvailabilities = {
  weekStart: "2026-11-09",
  weekEnd: "2026-11-15",
  cycleId: null,
  cyclePhase: null,
  instructors: [],
};

describe("coordination API", () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
  });

  it("cria o ciclo com POST e corpo weekStart", async () => {
    mocks.apiRequest.mockResolvedValue(cycle);
    const api = createRealApi();

    const result = await api.coordination.createCycle({ weekStart: "2026-11-09" });

    expect(mocks.apiRequest).toHaveBeenCalledWith("/coordination/cycles", {
      method: "POST",
      body: { weekStart: "2026-11-09" },
    });
    expect(result).toEqual(cycle);
  });

  it("consulta as disponibilidades por GET, preservando o cancelamento", async () => {
    mocks.apiRequest.mockResolvedValue(availabilities);
    const api = createRealApi();
    const controller = new AbortController();

    const result = await api.coordination.listAvailabilities(
      "2026-11-09",
      controller.signal,
    );

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/coordination/cycles/2026-11-09/availabilities",
      { signal: controller.signal },
    );
    expect(result).toEqual(availabilities);
  });

  it("codifica a semana no caminho da consulta", async () => {
    mocks.apiRequest.mockResolvedValue(availabilities);
    const api = createRealApi();

    await api.coordination.listAvailabilities("2026-11-09/extra");

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/coordination/cycles/2026-11-09%2Fextra/availabilities",
      { signal: undefined },
    );
  });
});
