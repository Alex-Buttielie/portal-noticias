"use client";

// Provider + hook do perfil de dispositivo.
// - Expõe `useDispositivo()` para qualquer componente cliente.
// - Espelha o perfil em `data-*` no <html> para CSS adaptar sem JS:
//   data-classe="mobile|tablet|desktop|tv", data-so, data-entrada,
//   data-orientacao, data-nav="trilho|inferior|nenhuma".
// - SSR: usa `perfilInicial` (do servidor via UA) até hidratar.

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { modoNavegacao, observarDispositivo } from "./detectar";
import { PERFIL_PADRAO_DESKTOP, type PerfilDispositivo } from "./tipos";

const DispositivoContext = createContext<PerfilDispositivo>(PERFIL_PADRAO_DESKTOP);

export function DeviceProvider({
  children,
  perfilInicial,
}: {
  children: ReactNode;
  perfilInicial?: PerfilDispositivo;
}) {
  const [perfil, setPerfil] = useState<PerfilDispositivo>(
    perfilInicial ?? PERFIL_PADRAO_DESKTOP
  );

  useEffect(() => observarDispositivo(setPerfil), []);

  // Espelha em atributos para o CSS reagir sem re-render.
  useEffect(() => {
    try {
      const el = document.documentElement;
      el.setAttribute("data-classe", perfil.classe);
      el.setAttribute("data-so", perfil.so);
      el.setAttribute("data-entrada", perfil.entrada);
      el.setAttribute("data-orientacao", perfil.orientacao);
      el.setAttribute("data-nav", modoNavegacao(perfil));
    } catch {
      /* DOM indisponível em testes */
    }
  }, [perfil]);

  const valor = useMemo(() => perfil, [perfil]);
  return (
    <DispositivoContext.Provider value={valor}>
      {children}
    </DispositivoContext.Provider>
  );
}

export function useDispositivo(): PerfilDispositivo {
  return useContext(DispositivoContext);
}

/** Atalhos legíveis para condicionais simples. */
export function useClasseDispositivo() {
  const { classe } = useDispositivo();
  return {
    classe,
    ehMobile: classe === "mobile",
    ehTablet: classe === "tablet",
    ehDesktop: classe === "desktop" || classe === "tv",
  };
}
