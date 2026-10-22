import { API_URL, REQUEST_TIMEOUT_MS } from "@/lib/config";
import {
  ApiError,
  fallbackMessage,
  kindFromStatus,
  messageFromBody,
} from "./errors";

type Query = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: Query): string {
  const url = new URL(`${API_URL}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== null && value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * Único ponto de saída HTTP do frontend.
 *
 * Segurança (premissas a confirmar com o backend):
 *  - a sessão é mantida por cookie `HttpOnly` definido pelo servidor
 *    (`credentials: "include"`); o frontend nunca lê nem guarda tokens;
 *  - o backend deve configurar CORS com origem explícita + credenciais e
 *    proteção contra CSRF para métodos não seguros.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!API_URL) {
    throw new ApiError("not_configured", fallbackMessage("not_configured"));
  }

  const { method = "GET", body, query, signal } = options;
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;

  let target: string;
  try {
    target = buildUrl(path, query);
  } catch {
    throw new ApiError("not_configured", fallbackMessage("not_configured"));
  }

  let response: Response;
  try {
    response = await fetch(target, {
      method,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: combined,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    if (timeout.aborted) {
      throw new ApiError("timeout", fallbackMessage("timeout"));
    }
    throw new ApiError("network", fallbackMessage("network"));
  }

  if (response.status === 204) return undefined as T;

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const kind = kindFromStatus(response.status);
    const { message, code } = messageFromBody(payload);
    throw new ApiError(kind, message ?? fallbackMessage(kind), {
      status: response.status,
      code,
      details: payload,
    });
  }

  return payload as T;
}
