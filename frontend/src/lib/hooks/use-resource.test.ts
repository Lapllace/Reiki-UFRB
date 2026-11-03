import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { useResource } from "./use-resource";

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

/**
 * Fetcher controlado: cada chamada fica pendente até o teste resolver/rejeitar.
 * Assim é possível afirmar exatamente quantas requisições foram disparadas.
 */
function manualFetcher() {
  const calls: Array<Deferred<string[]>> = [];
  const signals: AbortSignal[] = [];
  const fetcher = vi.fn((signal: AbortSignal) => {
    const call = deferred<string[]>();
    calls.push(call);
    signals.push(signal);
    return call.promise;
  });
  return { fetcher, calls, signals };
}

function renderResource() {
  const { fetcher, calls, signals } = manualFetcher();
  const view = renderHook(({ queryKey }: { queryKey: string }) => useResource(queryKey, fetcher), {
    initialProps: { queryKey: "key" },
  });
  return { ...view, fetcher, calls, signals };
}

/**
 * Conclui a primeira carga e espera o hook expor o estado final de verdade:
 * `loading` e `refreshing` falsos, com os dados da primeira requisição.
 */
async function renderLoadedResource() {
  const view = renderResource();

  await waitFor(() => expect(view.calls).toHaveLength(1));
  await act(async () => {
    view.calls[0].resolve(["initial"]);
  });
  await waitFor(() => {
    expect(view.result.current.loading).toBe(false);
    expect(view.result.current.refreshing).toBe(false);
    expect(view.result.current.data).toEqual(["initial"]);
  });
  expect(view.fetcher).toHaveBeenCalledTimes(1);

  return view;
}

describe("useResource.reloadAsync", () => {
  it("uma única chamada resolve true quando a atualização termina com sucesso", async () => {
    const { fetcher, calls, result } = await renderLoadedResource();

    let pending!: Promise<boolean>;
    act(() => {
      pending = result.current.reloadAsync();
    });

    // A recarga disparou exatamente uma nova requisição.
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    await act(async () => {
      calls[1].resolve(["updated"]);
      await pending;
    });

    await expect(pending).resolves.toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(result.current.data).toEqual(["updated"]);
    expect(result.current.error).toBeUndefined();
    expect(result.current.loading).toBe(false);
    expect(result.current.refreshing).toBe(false);
  });

  it("uma única chamada resolve false e expõe o erro quando a atualização falha", async () => {
    const { fetcher, calls, result } = await renderLoadedResource();

    let pending!: Promise<boolean>;
    act(() => {
      pending = result.current.reloadAsync();
    });

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    await act(async () => {
      calls[1].reject(new ApiError("network", "Sem conexão."));
      await pending;
    });

    await expect(pending).resolves.toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(result.current.error?.message).toBe("Sem conexão.");
    expect(result.current.data).toBeUndefined();
  });

  it("reload() continua recarregando em segundo plano, compatível com os componentes", async () => {
    const { fetcher, calls, result } = await renderLoadedResource();

    act(() => {
      result.current.reload();
    });

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    await act(async () => {
      calls[1].resolve(["updated"]);
    });

    await waitFor(() => expect(result.current.data).toEqual(["updated"]));
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(result.current.error).toBeUndefined();
  });

  it("descarta a resposta de uma recarga antiga quando outra mais recente termina antes", async () => {
    const { fetcher, calls, result } = await renderLoadedResource();

    let pending!: Promise<boolean>;
    act(() => {
      pending = result.current.reloadAsync();
    });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    // Uma recarga mais nova substitui a anterior antes dela terminar.
    act(() => {
      result.current.reload();
    });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));

    await act(async () => {
      calls[2].resolve(["newest"]);
    });
    await waitFor(() => expect(result.current.data).toEqual(["newest"]));

    await expect(pending).resolves.toBe(false);

    // A resposta antiga chega depois e não pode sobrescrever a mais recente.
    await act(async () => {
      calls[1].resolve(["stale"]);
    });

    expect(result.current.data).toEqual(["newest"]);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("não aplica requisição pendente após trocar a chave", async () => {
    const { fetcher, calls, result, rerender } = await renderLoadedResource();

    let pending!: Promise<boolean>;
    act(() => {
      pending = result.current.reloadAsync();
    });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    rerender({ queryKey: "other" });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));

    await act(async () => {
      calls[2].resolve(["other"]);
    });
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.data).toEqual(["other"]);
    });

    await expect(pending).resolves.toBe(false);

    await act(async () => {
      calls[1].resolve(["stale-key"]);
    });

    expect(result.current.data).toEqual(["other"]);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("resolve a pendência como false ao desmontar e cancela a requisição", async () => {
    const { fetcher, calls, signals, result, unmount } = await renderLoadedResource();

    let pending!: Promise<boolean>;
    act(() => {
      pending = result.current.reloadAsync();
    });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    unmount();

    await expect(pending).resolves.toBe(false);
    expect(signals[1].aborted).toBe(true);

    // Mesmo que a resposta chegue depois, nada é aplicado.
    await act(async () => {
      calls[1].resolve(["late"]);
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
