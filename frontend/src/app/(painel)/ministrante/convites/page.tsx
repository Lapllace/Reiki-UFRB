import type { Metadata } from "next";
import { CoverInvites } from "@/components/painel/cover-invites";

export const metadata: Metadata = { title: "Convites de cobertura" };

export default function CoverInvitesPage() {
  return <CoverInvites />;
}
