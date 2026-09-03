"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";

export default function VerificarEmailConteudo() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [estado, setEstado] = useState<"carregando" | "sucesso" | "erro">("carregando");
  const [mensagem, setMensagem] = useState("");

  useEffect(() => {
    if (!token) {
      setEstado("erro");
      setMensagem("Link de verificação inválido — token não encontrado na URL.");
      return;
    }
    api
      .verificarEmail(token)
      .then((resposta) => {
        setEstado("sucesso");
        setMensagem(resposta.detail);
      })
      .catch((e: unknown) => {
        setEstado("erro");
        setMensagem(
          e instanceof api.ApiError ? e.message : "Não foi possível verificar o e-mail."
        );
      });
  }, [token]);

  return (
    <div className="formulario">
      <h1>Verificação de e-mail</h1>
      {estado === "carregando" && <p className="texto-suave">Verificando...</p>}
      {estado === "sucesso" && (
        <>
          <p className="mensagem-sucesso">{mensagem}</p>
          <Link href="/login" className="botao">
            Ir para o login
          </Link>
        </>
      )}
      {estado === "erro" && <p className="mensagem-erro">{mensagem}</p>}
    </div>
  );
}
