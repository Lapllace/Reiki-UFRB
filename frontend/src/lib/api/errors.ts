export type ApiErrorKind =
  | "not_configured"
  | "network"
  | "timeout"
  | "unauthenticated"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "server"
  | "unknown";

/** Erro padronizado de qualquer chamada à API (real ou de demonstração). */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  /** Código de negócio opcional enviado pelo backend (ex.: "session_full"). */
  readonly code: string | null;
  readonly details: unknown;

  constructor(
    kind: ApiErrorKind,
    message: string,
    options: { status?: number | null; code?: string | null; details?: unknown } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = options.status ?? null;
    this.code = options.code ?? null;
    this.details = options.details;
  }
}

export function kindFromStatus(status: number): ApiErrorKind {
  if (status === 401) return "unauthenticated";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 400 || status === 422) return "validation";
  if (status >= 500) return "server";
  return "unknown";
}

const FALLBACK_MESSAGES: Record<ApiErrorKind, string> = {
  not_configured:
    "A conexão com o servidor ainda não foi configurada. Defina NEXT_PUBLIC_API_URL para usar dados reais.",
  network:
    "Não foi possível conectar ao servidor. Verifique sua internet e tente novamente.",
  timeout: "O servidor demorou demais para responder. Tente novamente em instantes.",
  unauthenticated: "Sua sessão não está ativa. Entre novamente para continuar.",
  forbidden: "Você não tem permissão para realizar esta ação.",
  not_found: "Não encontramos o que você procura.",
  conflict: "O estado deste item mudou. Atualize a página e confira a situação atual.",
  validation: "Alguns dados não foram aceitos. Revise as informações e tente de novo.",
  server: "O servidor encontrou um problema. Tente novamente em instantes.",
  unknown: "Algo inesperado aconteceu. Tente novamente.",
};

export function fallbackMessage(kind: ApiErrorKind): string {
  return FALLBACK_MESSAGES[kind];
}

/** Normaliza qualquer valor lançado em um `ApiError`. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError("unknown", "Requisição cancelada.");
  }
  return new ApiError("unknown", fallbackMessage("unknown"));
}

/** Extrai uma mensagem legível do corpo de erro (formato `detail` do FastAPI). */
export function messageFromBody(body: unknown): { message: string | null; code: string | null } {
  if (!body || typeof body !== "object") return { message: null, code: null };
  const record = body as Record<string, unknown>;
  const code = typeof record.code === "string" ? record.code : null;
  const detail = record.detail ?? record.message;
  if (typeof detail === "string") return { message: detail, code };
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    if (first && typeof first.msg === "string") return { message: first.msg, code };
  }
  if (detail && typeof detail === "object") {
    const nested = detail as Record<string, unknown>;
    return {
      message: typeof nested.message === "string" ? nested.message : null,
      code: typeof nested.code === "string" ? nested.code : code,
    };
  }
  return { message: null, code };
}
