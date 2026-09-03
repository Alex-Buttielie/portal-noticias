"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";

export default function PaginaRecuperarSenha() {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const resposta = await api.recuperarSenha(email);
      setMensagem(resposta.detail);
    } catch (e) {
      setErro(
        e instanceof api.ApiError ? e.message : "Não foi possível processar o pedido."
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="formulario">
      <h1>Recuperar senha</h1>
      {erro && <p className="mensagem-erro">{erro}</p>}
      {mensagem ? (
        <p className="mensagem-sucesso">{mensagem}</p>
      ) : (
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
          <button type="submit" className="botao" disabled={enviando}>
            {enviando ? "Enviando..." : "Enviar instruções"}
          </button>
        </form>
      )}
    </div>
  );
}
