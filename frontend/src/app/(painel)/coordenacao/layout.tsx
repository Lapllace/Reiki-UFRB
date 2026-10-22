import type { Metadata } from "next";
import { PanelShell } from "@/components/layout/panel-shell";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function CoordinationLayout({ children }: { children: React.ReactNode }) {
  return <PanelShell role="coordinator">{children}</PanelShell>;
}
