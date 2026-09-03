"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import * as api from "./api";
import { importarPreferenciasDoBackendSeNecessario } from "./cookie-consent";

interface AuthContextValue {
  token: string | null;
  usuario: api.Usuario | null;
  carregando: boolean;
  fazerLogin: (email: string, senha: string) => Promise<void>;
  fazerLogout: () => Promise<void>;
  atualizarUsuario: (usuario: api.Usuario) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const CHAVE_TOKEN = "portal_noticias_token";
const CHAVE_USUARIO = "portal_noticias_usuario";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [usuario, setUsuario] = useState<api.Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    try {
      const tokenSalvo = window.localStorage.getItem(CHAVE_TOKEN);
      const usuarioSalvo = window.localStorage.getItem(CHAVE_USUARIO);
      if (tokenSalvo) {
        setToken(tokenSalvo);
        // code-review-contract.md (run 20260903-1134-seo-lgpd-design-system,
        // Finding 2): sessão já autenticada carregada (ex.: recarregar a
        // página, ou reabrir o app com token persistido) também é um ponto
        // onde a preferência de cookies pode nunca ter sido trazida do
        // backend ainda para este navegador — não só o login explícito
        // abaixo. `importarPreferenciasDoBackendSeNecessario` já é no-op se
        // já houver uma escolha local registrada.
        void importarPreferenciasDoBackendSeNecessario(tokenSalvo);
      }
      if (usuarioSalvo) setUsuario(JSON.parse(usuarioSalvo) as api.Usuario);
    } catch {
      // localStorage indisponível (ex.: modo privado) — segue sem sessão persistida.
    } finally {
      setCarregando(false);
    }
  }, []);

  const persistirSessao = useCallback((novoToken: string, novoUsuario: api.Usuario) => {
    setToken(novoToken);
    setUsuario(novoUsuario);
    try {
      window.localStorage.setItem(CHAVE_TOKEN, novoToken);
      window.localStorage.setItem(CHAVE_USUARIO, JSON.stringify(novoUsuario));
    } catch {
      // ignora falha de persistência — sessão continua válida em memória nesta aba.
    }
  }, []);

  const limparSessao = useCallback(() => {
    setToken(null);
    setUsuario(null);
    try {
      window.localStorage.removeItem(CHAVE_TOKEN);
      window.localStorage.removeItem(CHAVE_USUARIO);
    } catch {
      // ignora
    }
  }, []);

  const fazerLogin = useCallback(
    async (email: string, senha: string) => {
      const resposta = await api.login(email, senha);
      persistirSessao(resposta.token, resposta.usuario);
      // code-review-contract.md (run 20260903-1134-seo-lgpd-design-system,
      // Finding 2): traz a preferência de cookies já registrada no backend
      // para este dispositivo/navegador logo após o login bem-sucedido —
      // sem isso, um usuário autenticado que troca de dispositivo sempre
      // via o banner de novo mesmo já tendo respondido em outro lugar.
      // Best-effort (a própria função engole erro de rede/404) — não deve
      // bloquear nem falhar o login.
      void importarPreferenciasDoBackendSeNecessario(resposta.token);
    },
    [persistirSessao]
  );

  const fazerLogout = useCallback(async () => {
    if (token) {
      try {
        await api.logout(token);
      } catch {
        // mesmo que a chamada falhe (ex.: token já expirado no servidor), limpa a sessão local.
      }
    }
    limparSessao();
  }, [token, limparSessao]);

  const atualizarUsuario = useCallback((novoUsuario: api.Usuario) => {
    setUsuario(novoUsuario);
    try {
      window.localStorage.setItem(CHAVE_USUARIO, JSON.stringify(novoUsuario));
    } catch {
      // ignora
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ token, usuario, carregando, fazerLogin, fazerLogout, atualizarUsuario }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const contexto = useContext(AuthContext);
  if (!contexto) {
    throw new Error("useAuth precisa ser usado dentro de um AuthProvider.");
  }
  return contexto;
}
