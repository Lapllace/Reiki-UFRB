"use client";

/**
 * DEMONSTRAÇÃO — escolha de perfil fictício no lugar do login.
 * Só é carregado com IS_DEMO (desenvolvimento). Não é autenticação.
 */
import { useRouter } from "next/navigation";
import { CalendarCheck, ClipboardList, LayoutDashboard, type LucideIcon } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { homeForRole, useAuth } from "@/lib/auth/auth-context";
import type { Role } from "@/lib/types";
import { setProfile } from "./demo-controls";

const options: { role: Role; title: string; text: string; icon: LucideIcon }[] = [
  {
    role: "participant",
    title: "Participante",
    text: "Ana Beatriz — inscrições, fila de espera e avisos.",
    icon: CalendarCheck,
  },
  {
    role: "instructor",
    title: "Ministrante",
    text: "Helena — disponibilidade, sessões e convites de cobertura.",
    icon: ClipboardList,
  },
  {
    role: "coordinator",
    title: "Coordenação",
    text: "Paulo — ciclos, coberturas e reorganização.",
    icon: LayoutDashboard,
  },
];

export default function DemoLogin({ next }: { next: string | null }) {
  const { refresh } = useAuth();
  const router = useRouter();

  async function choose(role: Role) {
    setProfile(role);
    await refresh();
    router.replace(next ?? homeForRole(role));
  }

  return (
    <div className="space-y-5">
      <Alert tone="warning" title="Modo demonstração">
        Não há login real aqui. Escolha um perfil fictício para explorar a interface. Os dados são
        inventados e ficam apenas na memória do navegador.
      </Alert>
      <ul className="space-y-3">
        {options.map(({ role, title, text, icon: Icon }) => (
          <li key={role}>
            <button
              type="button"
              onClick={() => void choose(role)}
              className="flex min-h-20 w-full items-center gap-4 rounded-2xl border border-line-strong bg-paper p-4 text-left transition-colors hover:border-forest-400 hover:bg-sage-50"
            >
              <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-sage-100 text-forest-700">
                <Icon className="size-6" aria-hidden />
              </span>
              <span>
                <span className="block font-semibold text-forest-900">{title}</span>
                <span className="block text-sm text-ink-600">{text}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
