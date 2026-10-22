"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ComponentType, type ReactNode } from "react";
import {
  Bell,
  CalendarCheck,
  CalendarDays,
  CalendarRange,
  ClipboardList,
  History,
  LayoutDashboard,
  LogOut,
  Repeat2,
  ShieldAlert,
  Sprout,
  UserRoundCheck,
  UsersRound,
  type LucideProps,
} from "lucide-react";
import { Button, ButtonLink } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { Skeleton } from "@/components/ui/states";
import { ErrorState } from "@/components/ui/states";
import { homeForRole, roleLabels, useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import type { Role } from "@/lib/types";

interface PanelItem {
  href: string;
  label: string;
  icon: ComponentType<LucideProps>;
  /** `true` = só ativa na rota exata (página de resumo). */
  exact?: boolean;
}

const navByRole: Record<Role, PanelItem[]> = {
  participant: [
    { href: "/participante", label: "Resumo", icon: Sprout, exact: true },
    { href: "/participante/inscricoes", label: "Inscrições", icon: CalendarCheck },
    { href: "/participante/notificacoes", label: "Avisos", icon: Bell },
    { href: "/agenda", label: "Agenda", icon: CalendarDays },
  ],
  instructor: [
    { href: "/ministrante", label: "Resumo", icon: Sprout, exact: true },
    { href: "/ministrante/disponibilidade", label: "Disponibilidade", icon: CalendarRange },
    { href: "/ministrante/sessoes", label: "Minhas sessões", icon: UserRoundCheck },
    { href: "/ministrante/convites", label: "Convites", icon: ClipboardList },
  ],
  coordinator: [
    { href: "/coordenacao", label: "Visão geral", icon: LayoutDashboard, exact: true },
    { href: "/coordenacao/sessoes", label: "Sessões", icon: CalendarDays },
    { href: "/coordenacao/coberturas", label: "Coberturas", icon: UsersRound },
    { href: "/coordenacao/reorganizacao", label: "Reorganização", icon: Repeat2 },
    { href: "/coordenacao/historico", label: "Histórico", icon: History },
  ],
};

function PanelLoading() {
  return (
    <div role="status" className="mx-auto w-full max-w-5xl space-y-6 px-5 py-12">
      <span className="sr-only">Verificando seu acesso…</span>
      <Skeleton className="h-10 w-1/3" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

function AccessDenied({ role }: { role: Role | null }) {
  return (
    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center px-5 py-20 text-center">
      <span className="grid size-16 place-items-center rounded-full bg-clay-100 text-clay-600">
        <ShieldAlert className="size-7" aria-hidden />
      </span>
      <h1 className="display-md mt-6">Esta área não está disponível para o seu perfil</h1>
      <p className="mt-3 text-ink-600">
        O acesso é definido pelo servidor de acordo com o seu perfil. Se você acredita que deveria
        ter acesso, fale com a coordenação.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {role ? <ButtonLink href={homeForRole(role)}>Ir para a minha área</ButtonLink> : null}
        <ButtonLink href="/" variant="secondary">
          Voltar ao início
        </ButtonLink>
      </div>
    </div>
  );
}

/**
 * Estrutura dos painéis autenticados e proteção de rota no cliente.
 *
 * ATENÇÃO: esta verificação melhora a experiência (redirecionamento e mensagens),
 * mas NÃO é uma barreira de segurança. Toda API precisa validar sessão e perfil
 * no servidor; aqui só exibimos conteúdo depois que o servidor confirma o perfil.
 */
export function PanelShell({ role, children }: { role: Role; children: ReactNode }) {
  const { state, user, logout, refresh } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const anonymous = state.status === "anonymous";
  useEffect(() => {
    if (anonymous) router.replace(`/entrar?next=${encodeURIComponent(pathname)}`);
  }, [anonymous, pathname, router]);

  if (state.status === "loading" || anonymous) return <PanelLoading />;

  if (state.status === "error") {
    return (
      <div className="mx-auto w-full max-w-2xl px-5 py-16">
        <ErrorState error={state.error} onRetry={() => void refresh()} />
      </div>
    );
  }

  if (!user || user.role !== role) return <AccessDenied role={user?.role ?? null} />;

  const items = navByRole[role];
  const isActive = (item: PanelItem) =>
    item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);

  return (
    <div className="flex flex-1 flex-col bg-sand-50/50">
      <header className="sticky top-0 z-40 border-b border-line bg-ivory">
        <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-4 px-4 sm:px-8">
          <Link href="/" aria-label="Reiki UFRB — site público" className="rounded-lg py-2">
            <Logo />
          </Link>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-semibold leading-tight text-forest-900">{user.name}</p>
              <p className="text-xs text-ink-600">{roleLabels[user.role]}</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void logout().then(() => router.replace("/"))}
              icon={<LogOut className="size-4" aria-hidden />}
            >
              Sair
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-10 px-4 pb-28 pt-8 sm:px-8 lg:pb-12">
        <aside className="hidden w-60 shrink-0 lg:block">
          <nav aria-label={`Área: ${roleLabels[role]}`} className="sticky top-24 space-y-1">
            <p className="eyebrow mb-4 px-4">{roleLabels[role]}</p>
            {items.map((item) => {
              const Icon = item.icon;
              const active = isActive(item);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-12 items-center gap-3 rounded-xl px-4 text-[0.95rem] font-semibold transition-colors",
                    active
                      ? "bg-forest-700 text-ivory shadow-soft"
                      : "text-ink-700 hover:bg-sage-100 hover:text-forest-900",
                  )}
                >
                  <Icon className="size-5" aria-hidden />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main id="conteudo" className="min-w-0 flex-1">
          {children}
        </main>
      </div>

      <nav
        aria-label={`Área: ${roleLabels[role]}`}
        className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-ivory pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        <ul className="mx-auto flex max-w-xl justify-around px-1">
          {items.map((item) => {
            const Icon = item.icon;
            const active = isActive(item);
            return (
              <li key={item.href} className="min-w-0 flex-1">
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-16 flex-col items-center justify-center gap-1 px-1 text-[0.68rem] font-semibold leading-tight transition-colors",
                    active ? "text-forest-800" : "text-ink-600",
                  )}
                >
                  <span
                    className={cn(
                      "grid h-7 w-12 place-items-center rounded-full transition-colors",
                      active && "bg-sage-200",
                    )}
                  >
                    <Icon className="size-5" aria-hidden />
                  </span>
                  <span className="max-w-full truncate">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
