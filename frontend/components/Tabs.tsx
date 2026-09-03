"use client";

import { useId, useRef, useState, type ReactNode } from "react";

export interface AbaTab {
  chave: string;
  rotulo: ReactNode;
  conteudo: ReactNode;
  disabled?: boolean;
}

/**
 * Navegação entre painéis mutuamente exclusivos, padrão WAI-ARIA "Tabs"
 * (implementation-contract.md run 20260903-1134-seo-lgpd-design-system,
 * escopo D): setas esquerda/direita movem o foco entre abas (roving
 * tabindex — só a aba ativa tem `tabIndex=0`), `Home`/`End` vão para a
 * primeira/última aba habilitada.
 */
export default function Tabs({ abas, abaInicial }: { abas: AbaTab[]; abaInicial?: string }) {
  const [abaAtiva, setAbaAtiva] = useState(
    abaInicial || abas.find((a) => !a.disabled)?.chave || abas[0]?.chave
  );
  const grupoId = useId();
  const botoesRef = useRef<(HTMLButtonElement | null)[]>([]);

  function habilitadas() {
    return abas.map((aba, indice) => ({ aba, indice })).filter((x) => !x.aba.disabled);
  }

  function focarIndice(indice: number) {
    botoesRef.current[indice]?.focus();
    setAbaAtiva(abas[indice].chave);
  }

  function aoPressionarTecla(evento: React.KeyboardEvent, indiceAtual: number) {
    const validas = habilitadas();
    if (validas.length === 0) return;
    const posAtual = validas.findIndex((x) => x.indice === indiceAtual);

    if (evento.key === "ArrowRight") {
      evento.preventDefault();
      focarIndice(validas[(posAtual + 1) % validas.length].indice);
    } else if (evento.key === "ArrowLeft") {
      evento.preventDefault();
      focarIndice(validas[(posAtual - 1 + validas.length) % validas.length].indice);
    } else if (evento.key === "Home") {
      evento.preventDefault();
      focarIndice(validas[0].indice);
    } else if (evento.key === "End") {
      evento.preventDefault();
      focarIndice(validas[validas.length - 1].indice);
    }
  }

  const painelAtivo = abas.find((a) => a.chave === abaAtiva);

  return (
    <div>
      <div role="tablist" className="tabs-lista" aria-label="Abas">
        {abas.map((aba, indice) => {
          const ativa = aba.chave === abaAtiva;
          return (
            <button
              key={aba.chave}
              type="button"
              role="tab"
              ref={(el) => {
                botoesRef.current[indice] = el;
              }}
              id={`${grupoId}-aba-${aba.chave}`}
              aria-selected={ativa}
              aria-controls={`${grupoId}-painel-${aba.chave}`}
              tabIndex={ativa ? 0 : -1}
              className="tabs-aba"
              disabled={aba.disabled}
              onClick={() => setAbaAtiva(aba.chave)}
              onKeyDown={(evento) => aoPressionarTecla(evento, indice)}
            >
              {aba.rotulo}
            </button>
          );
        })}
      </div>
      {painelAtivo && (
        <div
          role="tabpanel"
          id={`${grupoId}-painel-${painelAtivo.chave}`}
          aria-labelledby={`${grupoId}-aba-${painelAtivo.chave}`}
          className="tabs-painel"
          tabIndex={0}
        >
          {painelAtivo.conteudo}
        </div>
      )}
    </div>
  );
}
