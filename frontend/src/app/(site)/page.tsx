import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  CalendarDays,
  CalendarSearch,
  Check,
  Footprints,
  HandHeart,
  HeartHandshake,
  Hourglass,
  Leaf,
  ShieldCheck,
  Wind,
} from "lucide-react";
import { FaqList } from "@/components/site/faq-list";
import { LocationsList } from "@/components/site/locations-list";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PendingValue, ProvisionalNote } from "@/components/ui/provisional";
import { Container, SectionHeading } from "@/components/ui/section";
import { faq } from "@/content/faq";

const sessionSteps = [
  {
    title: "Acolhimento",
    text: "Você é recebido(a) no local indicado na agenda e pode tirar dúvidas antes de começar.",
  },
  {
    title: "Acomodação",
    text: "Em geral, a pessoa fica vestida, sentada ou deitada de forma confortável, em um ambiente calmo.",
  },
  {
    title: "Prática",
    text: "O ministrante posiciona as mãos suavemente sobre ou próximo ao corpo. Se algo causar desconforto, basta avisar.",
  },
  {
    title: "Encerramento",
    text: "A sessão termina com um momento para voltar com calma e retomar as atividades.",
  },
];

const pillars = [
  {
    icon: HandHeart,
    title: "Mãos e presença",
    text: "A prática se apoia em um toque leve, ou na proximidade das mãos, e na atenção de quem conduz.",
  },
  {
    icon: Wind,
    title: "Ambiente tranquilo",
    text: "Um espaço sem pressa, pensado para desacelerar e descansar por alguns minutos.",
  },
  {
    icon: Leaf,
    title: "Origem japonesa",
    text: "Difundido a partir do início do século XX, o Reiki hoje é conhecido em vários países como prática complementar de bem-estar.",
  },
];

const benefits = [
  {
    icon: Wind,
    title: "Uma pausa no ritmo do dia",
    text: "Pode ser um momento dedicado a desacelerar, respirar e descansar.",
  },
  {
    icon: HeartHandshake,
    title: "Atenção ao momento presente",
    text: "O ambiente calmo favorece perceber a respiração e as sensações do corpo.",
  },
  {
    icon: ShieldCheck,
    title: "Cuidado complementar",
    text: "Pode caminhar ao lado do cuidado em saúde, nunca no lugar dele.",
  },
];

const firstTime = [
  "Consulte a agenda e confira data, horário e local antes de sair de casa.",
  "Prefira roupas confortáveis.",
  "Se você acompanha alguma condição de saúde, mantenha o tratamento e, se quiser, converse com o ministrante antes da sessão.",
  "Se não puder comparecer, cancele a inscrição na sua área para liberar a vaga a outra pessoa.",
];

export default function HomePage() {
  return (
    <>
      {/* Abertura */}
      <section className="relative overflow-hidden">
        <Container className="grid items-center gap-14 pb-20 pt-10 sm:pt-14 lg:grid-cols-12 lg:gap-10 lg:pb-28 lg:pt-20">
          <div className="lg:col-span-7">
            <p className="eyebrow animate-rise">Reiki · bem-estar e cuidado</p>
            <h1 className="display-xl mt-6 animate-rise [animation-delay:90ms]">
              Um momento de calma,{" "}
              <em className="font-normal italic text-forest-600">cuidado</em> e presença.
            </h1>
            <p className="lead mt-7 max-w-xl animate-rise [animation-delay:180ms]">
              Conheça o Reiki, consulte a agenda semanal e inscreva-se em uma sessão. Tudo com
              informações claras, sem promessas de cura e com acolhimento.
            </p>
            <div className="mt-10 flex flex-col gap-3 animate-rise [animation-delay:270ms] sm:flex-row">
              <ButtonLink
                href="/agenda"
                size="lg"
                icon={<CalendarDays className="size-5" aria-hidden />}
              >
                Consultar a agenda
              </ButtonLink>
              <ButtonLink href="/sobre-reiki" size="lg" variant="secondary">
                Conhecer o Reiki
              </ButtonLink>
            </div>
            <ul className="mt-12 grid gap-4 text-[0.95rem] text-ink-700 animate-rise [animation-delay:360ms] sm:grid-cols-3">
              {[
                { icon: CalendarSearch, text: "Agenda atualizada a cada semana" },
                { icon: Check, text: "Inscrição simples e confirmada pelo sistema" },
                { icon: ShieldCheck, text: "Informação responsável, sem promessas de cura" },
              ].map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-sage-100 text-forest-700">
                    <Icon className="size-4" aria-hidden />
                  </span>
                  <span className="pt-1.5 leading-snug">{text}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="relative mx-auto w-full max-w-md animate-rise [animation-delay:200ms] lg:col-span-5 lg:max-w-none">
            <div
              aria-hidden
              className="absolute -right-5 -top-5 size-44 rounded-full bg-lavender-100 sm:-right-8 sm:-top-8 sm:size-56"
            />
            <div className="relative aspect-4/5 overflow-hidden rounded-t-[999px] rounded-b-[2.25rem] shadow-lift">
              <Image
                src="/images/hero-margarida.jpg"
                alt="Uma mão aberta segura uma pequena margarida contra a luz suave do pôr do sol."
                fill
                priority
                sizes="(min-width: 1024px) 38vw, 90vw"
                className="object-cover object-[38%_50%]"
              />
            </div>
            <Link
              href="/agenda"
              className="group absolute -bottom-6 left-0 flex items-center gap-4 rounded-2xl border border-line bg-paper p-4 pr-6 shadow-lift transition-transform hover:-translate-y-0.5 sm:-left-8"
            >
              <span className="grid size-12 place-items-center rounded-xl bg-forest-700 text-ivory">
                <CalendarDays className="size-6" aria-hidden />
              </span>
              <span>
                <span className="block text-sm text-ink-600">Próximos horários</span>
                <span className="flex items-center gap-1.5 font-semibold text-forest-900">
                  Ver agenda da semana
                  <ArrowRight
                    className="size-4 transition-transform group-hover:translate-x-1"
                    aria-hidden
                  />
                </span>
              </span>
            </Link>
          </div>
        </Container>
      </section>

      {/* Propósito */}
      <section className="py-20 sm:py-28" aria-labelledby="proposito">
        <Container className="grid items-center gap-14 lg:grid-cols-12 lg:gap-20">
          <div className="relative lg:col-span-5">
            <div className="relative aspect-4/5 overflow-hidden rounded-[2rem] shadow-soft">
              <Image
                src="/images/arvore-raizes.jpg"
                alt="Uma grande figueira com raízes amplas e raios de sol entre as folhas."
                fill
                sizes="(min-width: 1024px) 38vw, 90vw"
                className="object-cover"
              />
            </div>
          </div>
          <div className="lg:col-span-7">
            <SectionHeading
              eyebrow="Propósito"
              title={<span id="proposito">Reunir cuidado, informação e organização em um só lugar.</span>}
              description="Esta plataforma existe para que participantes, ministrantes e coordenação cuidem das sessões de Reiki com clareza: quem pode participar, quando e onde acontecem, e o que fazer quando algo muda."
            />
            <ul className="mt-10 grid gap-6 sm:grid-cols-2">
              <li className="border-l-2 border-sage-300 pl-5">
                <p className="font-display text-xl text-forest-900">Para quem participa</p>
                <p className="mt-1.5 text-ink-700">
                  Encontrar uma sessão, se inscrever e acompanhar tudo pela sua área pessoal.
                </p>
              </li>
              <li className="border-l-2 border-lavender-300 pl-5">
                <p className="font-display text-xl text-forest-900">Para quem conduz</p>
                <p className="mt-1.5 text-ink-700">
                  Registrar a disponibilidade da semana e responder a convites de cobertura.
                </p>
              </li>
            </ul>
            <ProvisionalNote className="mt-10">
              <strong className="font-semibold">Texto provisório.</strong> A missão e a descrição
              institucional do projeto serão confirmadas pela coordenação.
            </ProvisionalNote>
          </div>
        </Container>
      </section>

      {/* O que é Reiki */}
      <section className="bg-sand-50 py-20 sm:py-28" aria-labelledby="o-que-e">
        <Container>
          <SectionHeading
            eyebrow="O que é Reiki"
            title={<span id="o-que-e">Uma prática de bem-estar baseada em mãos e atenção.</span>}
            description="Reiki é uma prática complementar de origem japonesa. Em uma sessão, a pessoa que conduz posiciona as mãos suavemente sobre ou perto do corpo de quem recebe, em silêncio ou com poucas palavras."
          />
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {pillars.map(({ icon: Icon, title, text }) => (
              <Card key={title} className="h-full">
                <span className="grid size-12 place-items-center rounded-2xl bg-sage-100 text-forest-700">
                  <Icon className="size-6" aria-hidden />
                </span>
                <h3 className="mt-6 font-display text-2xl text-forest-900">{title}</h3>
                <p className="mt-3 text-ink-700">{text}</p>
              </Card>
            ))}
          </div>
          <div className="mt-10">
            <ButtonLink
              href="/sobre-reiki"
              variant="secondary"
              icon={<ArrowRight className="size-4" aria-hidden />}
            >
              Ler mais sobre o Reiki
            </ButtonLink>
          </div>
        </Container>
      </section>

      {/* Como funciona uma sessão */}
      <section
        data-surface="dark"
        className="relative overflow-hidden bg-forest-900 py-20 text-ivory sm:py-28"
        aria-labelledby="como-sessao"
      >
        <Container className="grid items-start gap-14 lg:grid-cols-12 lg:gap-16">
          <div className="lg:col-span-5 lg:sticky lg:top-28">
            <SectionHeading
              tone="dark"
              eyebrow="Como funciona uma sessão"
              title={<span id="como-sessao">Passo a passo, sem pressa.</span>}
              description="Uma visão geral de como costuma ser o encontro. Os detalhes de cada sessão aparecem na agenda."
            />
            <div className="relative mt-10 hidden aspect-4/3 overflow-hidden rounded-3xl lg:block">
              <Image
                src="/images/sessao-luz.jpg"
                alt="Mãos posicionadas com delicadeza próximas ao rosto de uma pessoa, sob uma luz quente e suave."
                fill
                sizes="40vw"
                className="object-cover"
              />
            </div>
          </div>
          <div className="lg:col-span-7">
            <ol className="space-y-5">
              {sessionSteps.map((step, index) => (
                <li
                  key={step.title}
                  className="flex gap-5 rounded-3xl border border-forest-700 bg-forest-800/60 p-6 sm:gap-7 sm:p-8"
                >
                  <span
                    aria-hidden
                    className="font-display text-5xl leading-none text-sage-300 sm:text-6xl"
                  >
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <h3 className="font-display text-2xl text-ivory">{step.title}</h3>
                    <p className="mt-2 text-forest-100">{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
            <p className="mt-6 flex flex-wrap items-center gap-2 text-sm text-forest-200">
              <Hourglass className="size-4" aria-hidden />
              Duração e rotina específica de cada sessão: <PendingValue />
            </p>
          </div>
        </Container>
      </section>

      {/* Benefícios e objetivos */}
      <section className="py-20 sm:py-28" aria-labelledby="beneficios">
        <Container>
          <SectionHeading
            eyebrow="Objetivos e expectativas"
            title={<span id="beneficios">O que esperar, com realismo.</span>}
            description="O Reiki é oferecido aqui como um momento de relaxamento e cuidado. Não há promessa de cura nem de resultados clínicos."
          />
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {benefits.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-(--radius-card) border border-lavender-200 bg-lavender-50 p-6 sm:p-8">
                <Icon className="size-7 text-lavender-700" aria-hidden />
                <h3 className="mt-5 font-display text-2xl text-forest-900">{title}</h3>
                <p className="mt-3 text-ink-700">{text}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 rounded-(--radius-card) border border-clay-200 bg-clay-50/70 p-6 sm:p-8">
            <h3 className="font-display text-xl text-forest-900">Importante</h3>
            <p className="mt-2 max-w-3xl text-ink-700">
              O Reiki não substitui consultas, exames, medicamentos nem acompanhamento psicológico ou
              psiquiátrico, e não deve ser usado para adiar ou interromper tratamentos. Em caso de
              dúvida sobre a sua saúde, procure um profissional.
            </p>
          </div>
        </Container>
      </section>

      {/* Primeira vez */}
      <section className="bg-sage-50 py-20 sm:py-28" aria-labelledby="primeira-vez">
        <Container className="grid items-center gap-14 lg:grid-cols-12 lg:gap-16">
          <div className="lg:col-span-6">
            <SectionHeading
              eyebrow="Primeira vez?"
              title={<span id="primeira-vez">Orientações para quem vai participar pela primeira vez.</span>}
              description="Sugestões gerais para você chegar tranquilo(a). Orientações específicas, quando existirem, aparecerão na agenda."
            />
            <ul className="mt-10 space-y-4">
              {firstTime.map((item) => (
                <li key={item} className="flex gap-4">
                  <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-forest-700 text-ivory">
                    <Check className="size-4" aria-hidden />
                  </span>
                  <span className="text-ink-800">{item}</span>
                </li>
              ))}
              <li className="flex gap-4">
                <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-honey-100 text-honey-700">
                  <Footprints className="size-4" aria-hidden />
                </span>
                <span className="text-ink-800">
                  Chegada e atrasos: <PendingValue />
                </span>
              </li>
            </ul>
          </div>
          <div className="lg:col-span-6">
            <div className="relative aspect-4/3 overflow-hidden rounded-[2rem] shadow-soft">
              <Image
                src="/images/trilha-floresta.jpg"
                alt="Uma trilha de terra cercada por árvores altas em uma floresta iluminada pelo sol."
                fill
                sizes="(min-width: 1024px) 45vw, 90vw"
                className="object-cover"
              />
            </div>
          </div>
        </Container>
      </section>

      {/* Locais */}
      <section className="py-20 sm:py-28" aria-labelledby="locais">
        <Container>
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <SectionHeading
              eyebrow="Onde acontecem"
              title={<span id="locais">Locais das sessões</span>}
              description="Endereços e referências são divulgados pela coordenação."
            />
            <ButtonLink href="/locais" variant="secondary" className="self-start sm:self-auto">
              Ver todos os locais
            </ButtonLink>
          </div>
          <div className="mt-12">
            <LocationsList variant="preview" limit={3} />
          </div>
        </Container>
      </section>

      {/* Perguntas frequentes */}
      <section className="bg-sand-50 py-20 sm:py-28" aria-labelledby="faq">
        <Container className="grid gap-12 lg:grid-cols-12 lg:gap-16">
          <div className="lg:col-span-4">
            <SectionHeading
              eyebrow="Perguntas frequentes"
              title={<span id="faq">Dúvidas comuns</span>}
              description="Não encontrou o que procurava? Os canais de contato serão divulgados pela coordenação."
            />
          </div>
          <div className="lg:col-span-8">
            <FaqList items={faq} />
          </div>
        </Container>
      </section>

      {/* Chamada final */}
      <section className="py-20 sm:py-28">
        <Container>
          <div
            data-surface="dark"
            className="relative overflow-hidden rounded-[2rem] bg-forest-800 px-6 py-16 text-center text-ivory sm:px-16 sm:py-24"
          >
            <div
              aria-hidden
              className="absolute -left-16 -top-16 size-64 rounded-full bg-forest-700/60"
            />
            <div
              aria-hidden
              className="absolute -bottom-24 -right-10 size-72 rounded-full bg-lavender-700/30"
            />
            <div className="relative mx-auto max-w-2xl">
              <h2 className="display-lg text-ivory">Veja os horários desta semana.</h2>
              <p className="lead mt-5 text-forest-100">
                Escolha uma sessão com calma, confira local e ministrante e confirme a sua inscrição.
              </p>
              <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <ButtonLink
                  href="/agenda"
                  variant="light"
                  size="lg"
                  icon={<CalendarDays className="size-5" aria-hidden />}
                >
                  Conhecer os horários
                </ButtonLink>
                <ButtonLink href="/como-funciona" variant="outline-light" size="lg">
                  Entender o processo
                </ButtonLink>
              </div>
            </div>
          </div>
        </Container>
      </section>
    </>
  );
}
