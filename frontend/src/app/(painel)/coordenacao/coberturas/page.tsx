import type { Metadata } from "next";
import { CoordinationCovers } from "@/components/painel/coordination-covers";

export const metadata: Metadata = { title: "Coberturas" };

export default function CoordinationCoversPage() {
  return <CoordinationCovers />;
}
