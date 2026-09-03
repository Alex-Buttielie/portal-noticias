"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";

export default function PaginaSolicitarCredenciamento() {
  const router = useRouter();
  const { token, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();

  const [telefone, setTelefone] = useState("");
  const [cidade, setCidade] = useState("");
  const [uf, setUf] = useState("");
  const [miniBio, setMiniBio] = useState("");
  const [dadosProfissionais, setDadosProfissionais] = useState("");
  const [documento, setDocumento] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);

    if (!token) return;
    if (!documento) {
      setErro("Anexe o documento comprobatório (diploma ou registro profissional).");
      return;
    }

    setEnviando(true);
    try {
      await api.solicitarCredenciamento(token, {
        telefone,
        cidade,
        uf,
        mini_bio: miniBio,
        dados_profissionais: dadosProfissionais,
        documento,
      });
      setSucesso(true);
      notificar("Solicitação de credenciamento enviada.", "sucesso");
    } catch (e) {
      const mensagem = e instanceof api.ApiError ? e.message : "Não foi possível enviar a solicitação.";
      setErro(mensagem);
      notificar(mensagem, "erro");
    } finally {
      setEnviando(false);
    }
  }

  if (sucesso) {
    return (
      <div className="formulario">
        <h1>Solicitação enviada</h1>
        <p className="mensagem-sucesso">
          Sua solicitação de credenciamento foi enviada e está em análise. Prazo de referência: até
          24h após o recebimento de documentação válida.
        </p>
      </div>
    );
  }

  return (
    <div className="formulario">
      <h1>Solicitar credenciamento de jornalista</h1>
      <p className="texto-suave">
        O credenciamento é manual — anexe um documento que comprove sua formação em Jornalismo ou
        registro profissional equivalente.
      </p>
      {erro && <p className="mensagem-erro">{erro}</p>}
      <form onSubmit={aoSubmeter}>
        <div className="campo">
          <label htmlFor="telefone">Telefone (opcional)</label>
          <input
            id="telefone"
            type="tel"
            placeholder="(11) 99999-0000"
            value={telefone}
            onChange={(e) => setTelefone(e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="cidade">Cidade</label>
          <input id="cidade" type="text" value={cidade} onChange={(e) => setCidade(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="uf">UF</label>
          <input
            id="uf"
            type="text"
            maxLength={2}
            value={uf}
            onChange={(e) => setUf(e.target.value.toUpperCase())}
          />
        </div>
        <div className="campo">
          <label htmlFor="mini-bio">Mini bio</label>
          <textarea id="mini-bio" rows={3} value={miniBio} onChange={(e) => setMiniBio(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="dados-profissionais">Dados profissionais</label>
          <textarea
            id="dados-profissionais"
            rows={3}
            placeholder="Formação, veículos onde já publicou, etc."
            value={dadosProfissionais}
            onChange={(e) => setDadosProfissionais(e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="documento">Documento comprobatório (PDF ou imagem)</label>
          <input
            id="documento"
            type="file"
            accept="application/pdf,image/*"
            onChange={(e) => setDocumento(e.target.files?.[0] || null)}
          />
        </div>
        <button type="submit" className="botao" disabled={enviando}>
          {enviando ? "Enviando..." : "Enviar solicitação"}
        </button>
      </form>
    </div>
  );
}
