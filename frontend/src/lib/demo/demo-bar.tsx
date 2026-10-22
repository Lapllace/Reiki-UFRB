"use client";

/**
 * DEMONSTRAÇÃO — barra para alternar perfis fictícios e simular falhas.
 * Só é carregada com IS_DEMO (desenvolvimento). Não representa login real.
 */
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";
import { FlaskConical } from "lucide-react";
import { homeForRole, useAuth } from "@/lib/auth/auth-context";
import {
  getControls,
  getServerSnapshot,
  setProfile,
  setSimulateError,
  subscribe,
  type DemoProfile,
} from "./demo-controls";

const profiles: { value: DemoProfile; label: string }[] = [
  { value: "visitor", label: "Visitante (sem login)" },
  { value: "participant", label: "Participante — Ana Beatriz" },
  { value: "instructor", label: "Ministrante — Helena" },
  { value: "coordinator", label: "Coordenação — Paulo" },
];

export default function DemoBar() {
  const controls = useSyncExternalStore(subscribe, getControls, getServerSnapshot);
  const { refresh } = useAuth();
  const router = useRouter();

  async function changeProfile(next: DemoProfile) {
    setProfile(next);
    await refresh();
    router.push(next === "visitor" ? "/" : homeForRole(next));
  }

  return (
    <section
      aria-label="Painel de demonstração"
      data-surface="dark"
      className="relative z-50 bg-ink-950 text-ivory"
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2 text-sm sm:px-8">
        <p className="flex items-center gap-2 font-semibold text-honey-200">
          <FlaskConical className="size-4" aria-hidden />
          Modo demonstração
          <span className="hidden font-normal text-forest-200 sm:inline">
            — dados fictícios em memória; nada é salvo nem enviado a um servidor.
          </span>
        </p>
        <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-2">
          <label className="flex items-center gap-2">
            <span className="text-forest-200">Ver como</span>
            <select
              value={controls.profile}
              onChange={(event) => void changeProfile(event.target.value as DemoProfile)}
              className="min-h-9 rounded-lg border border-forest-700 bg-forest-900 px-2 text-ivory"
            >
              {profiles.map((profile) => (
                <option key={profile.value} value={profile.value}>
                  {profile.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-h-9 cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={controls.simulateError}
              onChange={(event) => setSimulateError(event.target.checked)}
              className="size-4 accent-honey-200"
            />
            <span>Simular falha de rede</span>
          </label>
        </div>
      </div>
    </section>
  );
}
