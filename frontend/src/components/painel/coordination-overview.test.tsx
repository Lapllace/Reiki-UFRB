import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CyclePhase, WeeklyCycle } from "@/lib/types";
import { PhaseTracker } from "./coordination-overview";

const phaseLabels: Record<CyclePhase, string> = {
  collecting_availability: "Disponibilidades",
  enrollment_pending: "Agenda preparada, aguardando abertura das inscrições",
  enrollment_open: "Inscrições abertas",
  in_progress: "Semana em andamento",
  closed: "Encerrada",
};

const phaseOrder: CyclePhase[] = [
  "collecting_availability",
  "enrollment_pending",
  "enrollment_open",
  "in_progress",
  "closed",
];

function cycleFor(phase: CyclePhase): WeeklyCycle {
  return {
    weekStart: "2026-11-02",
    weekEnd: "2026-11-08",
    phase,
    availabilityDeadline: "2026-11-01T18:00:00-03:00",
    enrollmentOpensAt: "2026-11-02T08:00:00-03:00",
    totals: {
      sessions: 0,
      capacity: null,
      confirmed: null,
      waitlisted: null,
      uncovered: 0,
      openCoverRequests: 0,
      pendingReallocations: 0,
    },
    instructors: [],
  };
}

describe("PhaseTracker", () => {
  it.each(phaseOrder.map((phase, index) => [phase, index] as const))(
    "marca %s como a etapa atual na posição correta",
    (phase, expectedIndex) => {
      render(<PhaseTracker cycle={cycleFor(phase)} />);

      const steps = screen.getAllByRole("listitem");
      expect(steps).toHaveLength(5);
      expect(steps[expectedIndex]).toHaveAttribute("aria-current", "step");
      expect(within(steps[expectedIndex]).getByText(phaseLabels[phase])).toBeInTheDocument();

      steps.forEach((step, index) => {
        if (index !== expectedIndex) {
          expect(step).not.toHaveAttribute("aria-current");
        }
      });
    },
  );

  it("não apresenta enrollment_pending como inscrições abertas", () => {
    render(<PhaseTracker cycle={cycleFor("enrollment_pending")} />);

    const steps = screen.getAllByRole("listitem");
    const pendingStep = steps[phaseOrder.indexOf("enrollment_pending")];
    const openStep = steps[phaseOrder.indexOf("enrollment_open")];

    expect(pendingStep).toHaveAttribute("aria-current", "step");
    expect(within(pendingStep).getByText("Etapa atual")).toBeInTheDocument();

    expect(openStep).not.toHaveAttribute("aria-current");
    expect(within(openStep).getByText("Ainda não iniciada")).toBeInTheDocument();
    expect(within(openStep).getByText("Inscrições abertas")).toBeInTheDocument();
  });

  it("distingue as cinco etapas na ordem do ciclo", () => {
    render(<PhaseTracker cycle={cycleFor("in_progress")} />);

    const steps = screen.getAllByRole("listitem");
    expect(steps.map((step) => step.textContent)).toEqual([
      expect.stringContaining("Disponibilidades"),
      expect.stringContaining("Agenda preparada, aguardando abertura das inscrições"),
      expect.stringContaining("Inscrições abertas"),
      expect.stringContaining("Semana em andamento"),
      expect.stringContaining("Encerrada"),
    ]);
  });
});
