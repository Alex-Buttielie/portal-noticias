"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import { useListaEspera } from "@/lib/queries";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";

export default function PaginaListaDeEspera() {
  const inscrever = useListaEspera();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [interesses, setInteresses] = useState("");
  const [localidade, setLocalidade] = useState("");
  const [canalPreferido, setCanalPreferido] = useState("");
  const [aceiteComunicacao, setAceiteComunicacao] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setSucesso(null);

    if (!aceiteComunicacao) {
      setErro("É necessário aceitar receber comunicações para entrar na lista de espera.");
      return;
    }

    try {
      const resultado = await inscrever.mutateAsync({
        nome,
        email,
        interesses: interesses
          .split(",")
          .map((i) => i.trim())
          .filter(Boolean),
        localidade: localidade || undefined,
        canal_preferido: canalPreferido || undefined,
        aceite_comunicacao: aceiteComunicacao,
      });
      setSucesso(resultado.detail || "Inscrição realizada! Avisaremos você em breve.");
      setNome("");
      setEmail("");
      setInteresses("");
      setLocalidade("");
      setCanalPreferido("");
      setAceiteComunicacao(false);
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível enviar sua inscrição.");
    }
  }

  return (
    <div>
      <h1>Entre na lista de espera</h1>
      <p className="texto-suave">
        O Portal de Notícias agrupa notícias de várias fontes sobre o mesmo assunto, resume o essencial e
        mostra o que está em alta na sua região. Seja avisado assim que novas funcionalidades e regiões
        forem liberadas.
      </p>

      <div className="cartao">
        <strong>Como funciona</strong>
        <ol>
          <li>Nós agrupamos notícias de várias fontes sobre o mesmo fato.</li>
          <li>Você lê um resumo direto ao ponto, com link para as fontes originais.</li>
          <li>Assinantes Premium acompanham a evolução dos assuntos em alta por região.</li>
        </ol>
      </div>

      {erro && <ErrorState mensagem={erro} />}
      {sucesso && <p className="mensagem-sucesso">{sucesso}</p>}

      <form onSubmit={aoSubmeter} className="formulario">
        <CampoTexto id="nome" rotulo="Nome" required autoComplete="name" value={nome} onChange={(e) => setNome(e.target.value)} />
        <CampoTexto id="email" rotulo="E-mail" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <CampoTexto
          id="interesses"
          rotulo="Interesses (separados por vírgula)"
          placeholder="política, tecnologia, esportes"
          value={interesses}
          onChange={(e) => setInteresses(e.target.value)}
        />
        <CampoTexto
          id="localidade"
          rotulo="Localidade"
          placeholder="cidade, estado ou país"
          value={localidade}
          onChange={(e) => setLocalidade(e.target.value)}
        />
        <CampoSelecao id="canal" rotulo="Canal preferido" value={canalPreferido} onChange={(e) => setCanalPreferido(e.target.value)}>
          <option value="">Sem preferência</option>
          <option value="email">E-mail</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="push">Notificação push</option>
        </CampoSelecao>
        <div className="campo">
          <label>
            <input
              type="checkbox"
              checked={aceiteComunicacao}
              onChange={(e) => setAceiteComunicacao(e.target.checked)}
            />{" "}
            Aceito receber comunicações sobre o lançamento.
          </label>
        </div>
        <Button type="submit" carregando={inscrever.isPending}>
          Entrar na lista de espera
        </Button>
      </form>
    </div>
  );
}
