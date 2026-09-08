"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";

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
      {erro && <ErrorState mensagem={erro} />}
      {mensagem ? (
        <p className="mensagem-sucesso">{mensagem}</p>
      ) : (
        <form onSubmit={aoSubmeter}>
          <CampoTexto id="email" rotulo="E-mail" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" carregando={enviando}>
            Enviar instruções
          </Button>
        </form>
      )}
    </div>
  );
}
