"use client";

import { useEffect, useState } from "react";

/**
 * `true` só após a hidratação.
 *
 * Leituras de `localStorage` (sinais de engajamento, salvos, premium...)
 * durante a renderização divergem do SSR e quebram a hidratação
 * ("Text content did not match"). Gateie esses sinais com este hook para
 * que a primeira render do cliente seja idêntica à do servidor.
 */
export function useHidratado(): boolean {
  const [hidratado, setHidratado] = useState(false);
  useEffect(() => {
    setHidratado(true);
  }, []);
  return hidratado;
}
