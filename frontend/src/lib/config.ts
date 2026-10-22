/**
 * Configuração de ambiente centralizada.
 *
 * `NEXT_PUBLIC_*` são lidas em tempo de build e ficam visíveis no navegador:
 * NUNCA coloque segredos nelas.
 */

/** URL base do backend FastAPI, sem barra final. Vazia = não configurada. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");

/**
 * Modo de demonstração (dados fictícios, em memória). Use apenas para LÓGICA
 * em tempo de execução (ex.: textos).
 *
 * ATENÇÃO: para carregar código de demonstração (`import()`/`lazy()`), NÃO use
 * esta constante: repita a condição literal
 *   process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_DEMO_MODE === "true"
 * no próprio `if`/ternário. Constantes importadas de outro módulo não são
 * eliminadas pelo bundler e o código fictício vazaria para o bundle de produção.
 *
 * Só pode ser ligado fora de produção: em `next build`/`next start` o
 * `NODE_ENV` é "production" e a demonstração fica desligada.
 */
export const IS_DEMO: boolean =
  process.env.NODE_ENV !== "production" &&
  process.env.NEXT_PUBLIC_DEMO_MODE === "true";

/** Tempo máximo de espera por uma resposta da API. */
export const REQUEST_TIMEOUT_MS = 15_000;
