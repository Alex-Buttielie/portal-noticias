"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { queryKeys } from "@/lib/query-keys";

interface IdentidadeSessao {
  autenticada: boolean;
  usuarioId: number | null;
}

/**
 * Isola e remove dados entre sessões. A chave privada já contém somente
 * `usuarioId`; no logout/troca, cancelamos as requisições privadas e limpamos
 * todo o cache em memória antes que o usuário seguinte reutilize qualquer dado.
 */
export function QuerySessionBoundary({ children }: { children: ReactNode }) {
  const { token, usuario } = useAuth();
  const cliente = useQueryClient();
  const sessaoAnterior = useRef<IdentidadeSessao | null>(null);
  const autenticada = token !== null;
  const usuarioId = autenticada ? usuario?.id ?? null : null;

  useEffect(() => {
    const atual: IdentidadeSessao = { autenticada, usuarioId };
    const anterior = sessaoAnterior.current;
    const houveLogout = anterior?.autenticada === true && !atual.autenticada;
    const houveTroca =
      anterior?.autenticada === true &&
      anterior.usuarioId !== atual.usuarioId;

    if (houveLogout || houveTroca) {
      void cliente.cancelQueries({ queryKey: queryKeys.privadas() });
      cliente.clear();
    }

    sessaoAnterior.current = atual;
  }, [autenticada, cliente, usuarioId]);

  return children;
}
