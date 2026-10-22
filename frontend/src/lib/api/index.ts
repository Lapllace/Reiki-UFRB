import type { ReikiApi } from "./contract";
import { createRealApi } from "./services";

export type { ReikiApi } from "./contract";
export { ApiError, toApiError } from "./errors";

const realApi = createRealApi();
let demoApiPromise: Promise<ReikiApi> | null = null;

/**
 * Escolhe a implementação. A condição usa `process.env` diretamente (e não uma
 * constante importada) para que o bundler a resolva em tempo de build: em
 * produção ela vira `false`, o `import()` é eliminado e nenhum dado fictício chega
 * ao bundle. Mantenha esta forma literal. Veja `src/lib/config.ts`.
 */
async function resolveApi(): Promise<ReikiApi> {
  if (
    process.env.NODE_ENV !== "production" &&
    process.env.NEXT_PUBLIC_DEMO_MODE === "true"
  ) {
    demoApiPromise ??= import("@/lib/demo/demo-api").then((module) => module.demoApi);
    return demoApiPromise;
  }
  return realApi;
}

type AsyncFn = (...args: unknown[]) => Promise<unknown>;

function lazyGroup<K extends keyof ReikiApi>(group: K): ReikiApi[K] {
  return new Proxy({} as ReikiApi[K], {
    get(_target, method: string) {
      return async (...args: unknown[]) => {
        const impl = await resolveApi();
        const fn = (impl[group] as unknown as Record<string, AsyncFn>)[method];
        return fn(...args);
      };
    },
  });
}

/** Fachada única: telas e hooks importam apenas `api`. */
export const api: ReikiApi = {
  auth: lazyGroup("auth"),
  locations: lazyGroup("locations"),
  sessions: lazyGroup("sessions"),
  enrollments: lazyGroup("enrollments"),
  notifications: lazyGroup("notifications"),
  availability: lazyGroup("availability"),
  instructor: lazyGroup("instructor"),
  coordination: lazyGroup("coordination"),
};
