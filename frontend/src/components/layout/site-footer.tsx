import Link from "next/link";
import { Mail } from "lucide-react";
import { Logo } from "@/components/ui/logo";
import { Container } from "@/components/ui/section";
import { PendingValue } from "@/components/ui/provisional";
import { publicNav } from "./nav";

export function SiteFooter() {
  return (
    <footer data-surface="dark" className="mt-24 bg-forest-900 text-forest-100">
      <Container className="grid gap-12 py-16 md:grid-cols-12">
        <div className="md:col-span-5">
          <Logo tone="light" />
          <p className="mt-6 max-w-sm text-forest-200">
            Um espaço de acolhimento e cuidado: sessões de Reiki organizadas em ciclos semanais, com
            informações claras e inscrição simples.
          </p>
        </div>

        <nav aria-label="Rodapé" className="md:col-span-3">
          <h2 className="eyebrow text-sage-300">Navegação</h2>
          <ul className="mt-5 space-y-3">
            <li>
              <Link href="/" className="rounded text-forest-100 hover:text-white hover:underline">
                Início
              </Link>
            </li>
            {publicNav.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="rounded text-forest-100 hover:text-white hover:underline">
                  {item.label}
                </Link>
              </li>
            ))}
            <li>
              <Link href="/entrar" className="rounded text-forest-100 hover:text-white hover:underline">
                Entrar
              </Link>
            </li>
          </ul>
        </nav>

        <div className="md:col-span-4">
          <h2 className="eyebrow text-sage-300">Contato institucional</h2>
          <ul className="mt-5 space-y-3 text-forest-100">
            <li className="flex items-start gap-3">
              <Mail className="mt-1 size-4 shrink-0 text-sage-300" aria-hidden />
              <span>
                E-mail e telefone: <PendingValue>Serão divulgados pela coordenação</PendingValue>
              </span>
            </li>
          </ul>
        </div>
      </Container>

      <div className="border-t border-forest-800">
        <Container className="space-y-3 py-6 text-sm text-forest-200">
          <p>
            O Reiki é uma prática complementar de bem-estar e não substitui acompanhamento médico,
            psicológico ou psiquiátrico. Mantenha seus tratamentos em andamento.
          </p>
          <p className="text-forest-300">
            Fotografias: Unsplash (Unsplash License). Nome, textos e informações institucionais são
            provisórios até a confirmação da coordenação.
          </p>
        </Container>
      </div>
    </footer>
  );
}
