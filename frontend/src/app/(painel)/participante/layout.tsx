import type { Metadata } from "next";
import { PanelShell } from "@/components/layout/panel-shell";

export const metadata: Metadata = { robots: { index: false, follow: false } };

/**
 * Áreas autenticadas só exibem conteúdo depois que o servidor confirma sessão e
 * perfil (veja PanelShell). Por isso o conteúdo das páginas não faz parte do
 * shell estático e a validação de "navegação instantânea" não se aplica.
 */
export const instant = false;

export default function ParticipantLayout({ children }: { children: React.ReactNode }) {
  return <PanelShell role="participant">{children}</PanelShell>;
}
