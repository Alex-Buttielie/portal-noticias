"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import * as api from "@/lib/api";

export default function PaginaCadastro() {
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [aceiteTermos, setAceiteTermos] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);

    if (!aceiteTermos) {
      setErro("É necessário aceitar os termos de uso e a política de privacidade.");
      return;
    }

    setEnviando(true);
    try {
      await api.cadastrar({ email, nome, senha, aceite_termos: aceiteTermos });
      setSucesso(true);
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível concluir o cadastro.");
    } finally {
      setEnviando(false);
    }
  }

  if (sucesso) {
    return (
      <div className="formulario">
        <h1>Cadastro realizado</h1>
        <p className="mensagem-sucesso">
          Enviamos um e-mail de confirmação para <strong>{email}</strong>. Verifique sua caixa
          de entrada e clique no link para ativar sua conta.
        </p>
        <Link href="/login">Ir para o login</Link>
      </div>
    );
  }

  return (
    <div className="formulario">
      <h1>Criar conta</h1>
      {erro && <p className="mensagem-erro">{erro}</p>}
      <form onSubmit={aoSubmeter}>
        <div className="campo">
          <label htmlFor="nome">Nome</label>
          <input id="nome" type="text" value={nome} onChange={(e) => setNome(e.target.value)} />
        </div>
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
            minLength={8}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </div>
        <div className="campo">
          <label>
            <input
              type="checkbox"
              checked={aceiteTermos}
              onChange={(e) => setAceiteTermos(e.target.checked)}
              style={{ width: "auto", marginRight: "0.4rem" }}
            />
            Li e aceito os{" "}
            <Link href="/paginas/termos-de-uso" target="_blank" rel="noopener noreferrer">
              termos de uso
            </Link>{" "}
            e a{" "}
            <Link href="/privacidade/politica" target="_blank" rel="noopener noreferrer">
              política de privacidade
            </Link>
            .
          </label>
        </div>
        <button type="submit" className="botao" disabled={enviando}>
          {enviando ? "Enviando..." : "Cadastrar"}
        </button>
      </form>
      <p className="texto-suave" style={{ marginTop: "1rem" }}>
        Já tem conta? <Link href="/login">Entrar</Link>
      </p>
    </div>
  );
}
