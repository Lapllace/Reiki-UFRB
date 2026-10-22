import type { Metadata } from "next";
import { CalendarDays, Check, CircleAlert, Info } from "lucide-react";
import { InstitutionalValue } from "@/components/site/institutional-value";
import { PageHero } from "@/components/site/page-hero";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProvisionalBadge, ProvisionalNote } from "@/components/ui/provisional";
import { Container, SectionHeading } from "@/components/ui/section";
import { institutional } from "@/content/institutional";

export const metadata: Metadata = {
  title: "Sobre o Reiki",
  description:
    "O que é o Reiki, como costuma ser uma sessão, o que esperar e quais cuidados ter. Informações gerais e responsáveis.",
};

const expectations = [
  "Um ambiente calmo, com pouca conversa e sem pressa.",
  "Permanecer vestido(a) e confortável, sentado(a) ou deitado(a).",
  "Toque leve das mãos ou proximidade delas, sem manipulações intensas.",
  "Liberdade para avisar se algo causar desconforto ou se quiser interromper.",
];

const recommendations = [
  "Mantenha o acompanhamento de saúde que você já faz, inclusive medicamentos.",
  "O Reiki não substitui consulta médica, psicológica ou psiquiátrica.",
  "Se estiver em crise ou em sofrimento intenso, procure atendimento profissional.",
  "Converse com o ministrante se tiver alguma dúvida ou necessidade específica.",
];

export default function AboutReikiPage() {
  return (
    <>
      <PageHero
        eyebrow="Sobre o Reiki"
        title="Uma prática simples, feita com atenção e cuidado."
        description="Um resumo claro e responsável sobre o que é o Reiki, como costuma ser uma sessão e o que você pode esperar."
      />

      <section className="py-20 sm:py-24">
        <Container className="grid gap-14 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <SectionHeading eyebrow="O que é" title="Reiki em poucas palavras" />
            <div className="mt-6">
              <ProvisionalBadge />
            </div>
          </div>
          <div className="space-y-5 text-lg leading-relaxed text-ink-800 lg:col-span-7">
            <p>
              Reiki é uma prática complementar de bem-estar criada no Japão no início do século XX
              e difundida em muitos países. Em uma sessão, a pessoa que conduz posiciona as mãos
              suavemente sobre ou próximo ao corpo de quem recebe.
            </p>
            <p>
              Na tradição do Reiki, essa prática é associada à ideia de uma energia vital. Essa
              explicação faz parte da tradição e não é um conceito comprovado pela ciência. Aqui,
              o Reiki é apresentado como um momento de pausa, relaxamento e cuidado.
            </p>
            <p>
              A evidência científica sobre efeitos clínicos do Reiki é limitada e variada. Por isso
              não fazemos promessas de cura nem de resultados em saúde.
            </p>
            <ProvisionalNote>
              Este texto é uma descrição geral provisória, escrita enquanto a coordenação não
              confirma o texto institucional. Ele será revisado e substituído quando necessário.
            </ProvisionalNote>
          </div>
        </Container>
      </section>

      <section className="bg-sand-50 py-20 sm:py-24">
        <Container className="grid gap-12 lg:grid-cols-2">
          <Card>
            <h2 className="font-display text-3xl text-forest-900">Como costuma ser uma sessão</h2>
            <p className="mt-3 text-ink-700">
              Descrição geral da prática, que pode variar conforme o ministrante e o local.
            </p>
            <ul className="mt-6 space-y-4">
              {expectations.map((item) => (
                <li key={item} className="flex gap-3">
                  <Check className="mt-1 size-5 shrink-0 text-forest-600" aria-hidden />
                  <span className="text-ink-800">{item}</span>
                </li>
              ))}
            </ul>
            <div className="mt-6">
              <ProvisionalBadge />
            </div>
          </Card>

          <Card tone="sage">
            <h2 className="font-display text-3xl text-forest-900">Recomendações importantes</h2>
            <p className="mt-3 text-ink-700">Cuidados simples para participar com segurança.</p>
            <ul className="mt-6 space-y-4">
              {recommendations.map((item) => (
                <li key={item} className="flex gap-3">
                  <CircleAlert className="mt-1 size-5 shrink-0 text-lavender-700" aria-hidden />
                  <span className="text-ink-800">{item}</span>
                </li>
              ))}
            </ul>
          </Card>
        </Container>
      </section>

      <section className="py-20 sm:py-24">
        <Container>
          <SectionHeading
            eyebrow="Informações institucionais"
            title="O que já está confirmado e o que ainda não está."
            description="Não publicamos dados que ainda não foram informados pela coordenação. Quando uma informação for confirmada, ela passa a aparecer aqui."
          />
          <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-ink-700">
            <Info className="size-4" aria-hidden />
            Legenda:
            <Badge tone="forest">Confirmado</Badge>
            <Badge tone="honey">A confirmar</Badge>
          </div>
          <dl className="mt-8 divide-y divide-line overflow-hidden rounded-(--radius-card) border border-line bg-paper shadow-soft">
            {Object.values(institutional).map((field) => (
              <div key={field.label} className="grid gap-1 px-5 py-4 sm:grid-cols-5 sm:gap-6 sm:px-7">
                <dt className="font-semibold text-forest-900 sm:col-span-2">{field.label}</dt>
                <dd className="text-ink-800 sm:col-span-3">
                  <InstitutionalValue field={field} />
                </dd>
              </div>
            ))}
          </dl>
          <div className="mt-12 flex flex-col gap-3 sm:flex-row">
            <ButtonLink href="/agenda" icon={<CalendarDays className="size-5" aria-hidden />}>
              Consultar a agenda
            </ButtonLink>
            <ButtonLink href="/como-funciona" variant="secondary">
              Como participar
            </ButtonLink>
          </div>
        </Container>
      </section>
    </>
  );
}
