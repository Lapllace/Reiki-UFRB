"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LayoutDashboard, LogOut, Menu, X } from "lucide-react";
import { Button, ButtonLink } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { Skeleton } from "@/components/ui/states";
import { homeForRole, useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { publicNav } from "./nav";

export function SiteHeader() {
  const pathname = usePathname();
  const { state, user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  const accountActions =
    state.status === "loading" ? (
      <Skeleton className="h-11 w-28 rounded-full" />
    ) : user ? (
      <>
        <ButtonLink
          href={homeForRole(user.role)}
          variant="soft"
          size="sm"
          icon={<LayoutDashboard className="size-4" aria-hidden />}
        >
          Minha área
        </ButtonLink>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setMenuOpen(false);
            void logout();
          }}
          icon={<LogOut className="size-4" aria-hidden />}
        >
          Sair
        </Button>
      </>
    ) : (
      <>
        <ButtonLink href="/entrar" variant="ghost" size="sm">
          Entrar
        </ButtonLink>
        <ButtonLink href="/agenda" size="sm">
          Ver agenda
        </ButtonLink>
      </>
    );

  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-ivory/95">
      <div className="mx-auto flex h-18 w-full max-w-7xl items-center justify-between gap-6 px-5 sm:px-8 lg:px-12">
        <Link href="/" className="rounded-lg py-2" aria-label="Reiki UFRB — página inicial" onClick={() => setMenuOpen(false)}>
          <Logo />
        </Link>

        <nav aria-label="Principal" className="hidden items-center gap-1 lg:flex">
          {publicNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(item.href) ? "page" : undefined}
              className={cn(
                "relative rounded-full px-4 py-2.5 text-[0.95rem] font-semibold transition-colors",
                isActive(item.href)
                  ? "bg-sage-100 text-forest-900"
                  : "text-ink-700 hover:bg-sage-50 hover:text-forest-900",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 lg:flex">{accountActions}</div>

        <button
          type="button"
          className="grid size-12 place-items-center rounded-full text-forest-900 transition-colors hover:bg-sage-100 lg:hidden"
          aria-expanded={menuOpen}
          aria-controls="menu-movel"
          aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
          onClick={() => setMenuOpen((value) => !value)}
        >
          {menuOpen ? <X className="size-6" aria-hidden /> : <Menu className="size-6" aria-hidden />}
        </button>
      </div>

      <div
        id="menu-movel"
        hidden={!menuOpen}
        className="border-t border-line bg-ivory px-5 pb-6 pt-3 shadow-lift sm:px-8 lg:hidden"
      >
        <nav aria-label="Principal (móvel)" className="flex flex-col">
          {publicNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMenuOpen(false)}
              aria-current={isActive(item.href) ? "page" : undefined}
              className={cn(
                "flex min-h-14 items-center justify-between border-b border-line font-display text-2xl",
                isActive(item.href) ? "text-forest-700" : "text-forest-900",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row" onClick={(event) => {
          if ((event.target as HTMLElement).closest("a")) setMenuOpen(false);
        }}>
          {accountActions}
        </div>
      </div>
    </header>
  );
}
