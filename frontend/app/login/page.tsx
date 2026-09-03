"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import { ApiError } from "@/lib/api";

export default function PaginaLogin() {
  const router = useRouter();
  const { fazerLogin } = useAuth();
  const { notificar } = useToast();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await fazerLogin(email, senha);
      notificar("Login realizado com sucesso. Bem-vindo de volta!", "sucesso");
      router.push("/");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="formulario">
      <h1>Entrar</h1>
      {erro && <p className="mensagem-erro">{erro}</p>}
      <form onSubmit={aoSubmeter}>
        <div className="campo">
          <label htmlFor="email">E-mail</label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="senha">Senha</label>
          <input
            id="senha"
            type="password"
            required
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </div>
        <button type="submit" className="botao" disabled={enviando}>
          {enviando ? "Entrando..." : "Entrar"}
        </button>
      </form>
      <p className="texto-suave" style={{ marginTop: "1rem" }}>
        <Link href="/recuperar-senha">Esqueci minha senha</Link>
      </p>
      <p className="texto-suave">
        Não tem conta? <Link href="/cadastro">Cadastre-se</Link>
      </p>
    </div>
  );
}
