"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";

export default function RedefinirSenhaConteudo() {
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const [novaSenha, setNovaSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);

    if (!uid || !token) {
      setErro("Link de redefinição inválido — faltam parâmetros na URL.");
      return;
    }

    setEnviando(true);
    try {
      await api.redefinirSenha(uid, token, novaSenha);
      setSucesso(true);
    } catch (e) {
      setErro(
        e instanceof api.ApiError ? e.message : "Não foi possível redefinir a senha."
      );
    } finally {
      setEnviando(false);
    }
  }

  if (sucesso) {
    return (
      <div className="formulario">
        <h1>Senha redefinida</h1>
        <p className="mensagem-sucesso">Sua senha foi alterada com sucesso.</p>
        <Link href="/login" className="botao botao--primaria botao--medio">
          Ir para o login
        </Link>
      </div>
    );
  }

  return (
    <div className="formulario">
      <h1>Redefinir senha</h1>
      {(!uid || !token) && (
        <ErrorState mensagem="Este link parece inválido. Peça uma nova redefinição de senha." />
      )}
      {erro && <ErrorState mensagem={erro} />}
      <form onSubmit={aoSubmeter}>
        <CampoTexto
          id="nova-senha"
          rotulo="Nova senha"
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          value={novaSenha}
          onChange={(e) => setNovaSenha(e.target.value)}
        />
        <Button type="submit" carregando={enviando} disabled={!uid || !token}>
          Redefinir senha
        </Button>
      </form>
    </div>
  );
}
