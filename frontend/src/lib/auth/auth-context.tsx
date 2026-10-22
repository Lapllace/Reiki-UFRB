"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import { ApiError, toApiError } from "@/lib/api/errors";
import type { LoginInput, Role, User } from "@/lib/types";

type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: User }
  | { status: "anonymous" }
  | { status: "error"; error: ApiError };

interface AuthContextValue {
  state: AuthState;
  user: User | null;
  /** Reconsulta o servidor: é ele quem confirma identidade e perfil. */
  refresh: () => Promise<void>;
  login: (input: LoginInput) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function homeForRole(role: Role): string {
  switch (role) {
    case "participant":
      return "/participante";
    case "instructor":
      return "/ministrante";
    case "coordinator":
      return "/coordenacao";
  }
}

export const roleLabels: Record<Role, string> = {
  participant: "Participante",
  instructor: "Ministrante",
  coordinator: "Coordenação",
};

/**
 * Estado de autenticação derivado SEMPRE da resposta do servidor (`auth.me`).
 * Não há token, perfil ou flag de login guardados no navegador; o cookie de
 * sessão (a definir pelo backend) não é acessível ao JavaScript.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const refresh = useCallback(async () => {
    try {
      const user = await api.auth.me();
      setState(user ? { status: "authenticated", user } : { status: "anonymous" });
    } catch (error) {
      setState({ status: "error", error: toApiError(error) });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.auth.me().then(
      (user) => {
        if (cancelled) return;
        setState(user ? { status: "authenticated", user } : { status: "anonymous" });
      },
      (error: unknown) => {
        if (!cancelled) setState({ status: "error", error: toApiError(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (input: LoginInput) => {
    const user = await api.auth.login(input);
    setState({ status: "authenticated", user });
    return user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      setState({ status: "anonymous" });
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      user: state.status === "authenticated" ? state.user : null,
      refresh,
      login,
      logout,
    }),
    [state, refresh, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth deve ser usado dentro de <AuthProvider>.");
  return context;
}
