import type { Metadata } from "next";
import { InstructorHome } from "@/components/painel/instructor-home";

export const metadata: Metadata = { title: "Área do ministrante" };

export default function InstructorHomePage() {
  return <InstructorHome />;
}
