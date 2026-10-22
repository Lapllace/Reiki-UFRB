import type { Metadata } from "next";
import {
  CalendarDays,
  CalendarSearch,
  ClipboardCheck,
  MapPinned,
  MousePointerClick,
  PenLine,
  Repeat2,
  UserRoundCog,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { PageHero } from "@/components/site/page-hero";
import { EnrollmentBadge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Container, SectionHeading } from "@/components/ui/section";

export const metadata: Metadata = {
  title: "Como funciona",
  description:
    "Do primeiro olhar na agenda à confirmação da inscrição: veja o passo a passo para participar de uma sessão.",
};

interface Step {
  icon: LucideIcon;
  title: string;
  text: string;
}

const steps: Step[] = [
  {
    icon: CalendarSearch,
    title: "Consulte a agenda semanal",
    text: "A agenda mostra as sessões de cada semana, com dia, horário, local, ministrante e vagas. Use as setas para navegar entre semanas.",
  },
  {
    icon: MousePointerClick,
    title: "Escolha uma sessão disponível",
    text: "Abra os detalhes da sessão que combina com a sua rotina. Se ela estiver lotada, pode haver fila de espera.",
  },
  {
    icon: PenLine,
    title: "Realize a inscrição",
    text: "Entre na sua conta e confirme a inscrição. A vaga só é considerada sua depois da resposta do sistema.",
  },
  {
    icon: ClipboardCheck,
    title: "Confira a confirmação",
    text: "Você verá se ficou com a vaga ou na fila de espera. Tudo fica registrado na sua área pessoal.",
  },
  {
    icon: MapPinned,
    title: "Consulte o local e as atualizações",
    text: "Revise endereço, referências e avisos antes de ir. Se algo mudar, a atualização aparece na sua área.",
  },
];

const changes = [
  {
    icon: UsersRound,
    title: "Sessão cancelada",
    text: "Se um ministrante cancelar, o sistema procura outro ministrante para cobrir. Se ninguém assumir, a sessão é cancelada e você é avisado(a).",
  },
  {
    icon: UserRoundCog,
    title: "Mudança de ministrante",
    text: "Quando outro ministrante assume uma sessão, a mudança é informada no cartão da sessão e na sua área.",
  },
  {
    icon: Repeat2,
    title: "Reorganização de participantes",
    text: "Se uma sessão deixar de acontecer, a coordenação pode reorganizar participantes para uma sessão extra ou para semanas futuras.",
  },
];

export default function HowItWorksPage() {
  return (
    <>
      <PageHero
        eyebrow="Como funciona"
        title="Participar é simples: cinco passos."
        description="Da consulta à agenda até o dia da sessão, veja como o processo acontece e o que fazer quando surge um imprevisto."
      >
        <ButtonLink href="/agenda" icon={<CalendarDays className="size-5" aria-hidden />}>
          Ir para a agenda
        </ButtonLink>
      </PageHero>

      <section className="py-20 sm:py-24">
        <Container>
          <ol className="relative mx-auto max-w-3xl space-y-10">
            <span
              aria-hidden
              className="absolute bottom-6 left-7 top-6 hidden w-px bg-line-strong sm:block"
            />
            {steps.map((step, index) => {
              const Icon = step.icon;
              return (
                <li key={step.title} className="relative flex gap-5 sm:gap-8">
                  <span className="relative z-10 grid size-14 shrink-0 place-items-center rounded-full border-4 border-ivory bg-forest-700 text-ivory shadow-soft">
                    <Icon className="size-6" aria-hidden />
                  </span>
                  <div className="pt-1">
                    <p className="eyebrow">Passo {index + 1}</p>
                    <h2 className="mt-2 font-display text-2xl text-forest-900 sm:text-3xl">
                      {step.title}
                    </h2>
                    <p className="mt-3 max-w-xl text-ink-700">{step.text}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </Container>
      </section>

      <section className="bg-sand-50 py-20 sm:py-24">
        <Container>
          <SectionHeading
            eyebrow="Situação da inscrição"
            title="Como você acompanha cada inscrição."
            description="Cada inscrição tem uma situação clara, sempre definida pelo sistema."
          />
          <ul className="mt-12 grid gap-4 sm:grid-cols-2">
            {(
              [
                ["confirmed", "Você tem uma vaga garantida nessa sessão."],
                ["waitlisted", "A sessão estava lotada. Se uma vaga surgir, sua situação é atualizada."],
                ["attended", "A sessão já aconteceu e a sua participação foi registrada."],
                ["cancelled", "A inscrição foi cancelada por você ou pela organização."],
              ] as const
            ).map(([status, text]) => (
              <li key={status}>
                <Card className="h-full">
                  <EnrollmentBadge status={status} />
                  <p className="mt-4 text-ink-700">{text}</p>
                </Card>
              </li>
            ))}
          </ul>
        </Container>
      </section>

      <section className="py-20 sm:py-24">
        <Container>
          <SectionHeading
            eyebrow="Imprevistos"
            title="Quando algo muda, você é avisado(a)."
            description="Alterações decorrentes de imprevistos poderão ser comunicadas a você. Os detalhes de cada caso seguem as regras definidas pela coordenação."
          />
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {changes.map(({ icon: Icon, title, text }) => (
              <div
                key={title}
                className="rounded-(--radius-card) border border-lavender-200 bg-lavender-50 p-6 sm:p-8"
              >
                <Icon className="size-7 text-lavender-700" aria-hidden />
                <h3 className="mt-5 font-display text-2xl text-forest-900">{title}</h3>
                <p className="mt-3 text-ink-700">{text}</p>
              </div>
            ))}
          </div>
          <div className="mt-12">
            <ButtonLink href="/agenda" size="lg">
              Consultar a agenda semanal
            </ButtonLink>
          </div>
        </Container>
      </section>
    </>
  );
}
