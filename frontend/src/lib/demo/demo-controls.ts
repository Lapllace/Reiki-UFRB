/**
 * DEMONSTRAÇÃO — controles do painel de demonstração.
 * Este arquivo só é importado por código que existe apenas com IS_DEMO.
 */
import type { Role } from "@/lib/types";

export type DemoProfile = Role | "visitor";

interface Controls {
  profile: DemoProfile;
  simulateError: boolean;
}

const STORAGE_KEY = "reiki-demo-profile";
const listeners = new Set<() => void>();

let controls: Controls = { profile: "visitor", simulateError: false };
let hydrated = false;

function hydrate() {
  if (hydrated || typeof window === "undefined") return;
  hydrated = true;
  const stored = window.sessionStorage.getItem(STORAGE_KEY);
  if (stored === "participant" || stored === "instructor" || stored === "coordinator") {
    controls = { ...controls, profile: stored };
  }
}

export function getControls(): Controls {
  hydrate();
  return controls;
}

export function setProfile(profile: DemoProfile) {
  hydrate();
  controls = { ...controls, profile };
  window.sessionStorage.setItem(STORAGE_KEY, profile);
  listeners.forEach((listener) => listener());
}

export function setSimulateError(value: boolean) {
  hydrate();
  controls = { ...controls, simulateError: value };
  listeners.forEach((listener) => listener());
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const SERVER_SNAPSHOT: Controls = { profile: "visitor", simulateError: false };
export function getServerSnapshot(): Controls {
  return SERVER_SNAPSHOT;
}
