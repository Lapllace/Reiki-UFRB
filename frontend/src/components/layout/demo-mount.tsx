"use client";

import { lazy, Suspense } from "react";

/**
 * Carrega a barra de demonstração somente em desenvolvimento com
 * NEXT_PUBLIC_DEMO_MODE=true. A condição usa `process.env` literalmente para
 * ser resolvida em tempo de build: em produção o `import()` é descartado do
 * bundle. Mantenha esta forma literal (veja `src/lib/config.ts`).
 */
const DemoBar =
  process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_DEMO_MODE === "true"
    ? lazy(() => import("@/lib/demo/demo-bar"))
    : null;

export function DemoMount() {
  if (!DemoBar) return null;
  return (
    <Suspense fallback={null}>
      <DemoBar />
    </Suspense>
  );
}
