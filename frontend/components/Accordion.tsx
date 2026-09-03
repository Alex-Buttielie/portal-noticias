"use client";

import { useId, useState, type ReactNode } from "react";

export interface ItemAccordion {
  chave: string;
  titulo: ReactNode;
  conteudo: ReactNode;
  disabled?: boolean;
}

/**
 * Seções expansíveis/colapsáveis (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo D). Por padrão só um item
 * fica aberto por vez (`permitirMultiplos={false}`) — comportamento comum
 * de FAQ; passe `permitirMultiplos` para permitir vários abertos ao mesmo
 * tempo. Cada cabeçalho é um `<button>` real com `aria-expanded`/
 * `aria-controls`, então funciona com Enter/Espaço nativamente, sem
 * `onKeyDown` customizado.
 */
export default function Accordion({
  itens,
  permitirMultiplos = false,
  itemInicialAberto,
}: {
  itens: ItemAccordion[];
  permitirMultiplos?: boolean;
  itemInicialAberto?: string;
}) {
  const [abertos, setAbertos] = useState<Set<string>>(
    new Set(itemInicialAberto ? [itemInicialAberto] : [])
  );
  const grupoId = useId();

  function alternar(chave: string) {
    setAbertos((atual) => {
      const proximo = permitirMultiplos ? new Set(atual) : new Set<string>();
      if (atual.has(chave)) {
        proximo.delete(chave);
      } else {
        proximo.add(chave);
      }
      return proximo;
    });
  }

  return (
    <div>
      {itens.map((item) => {
        const aberto = abertos.has(item.chave);
        const cabecalhoId = `${grupoId}-cabecalho-${item.chave}`;
        const painelId = `${grupoId}-painel-${item.chave}`;
        return (
          <div className="accordion-item" key={item.chave}>
            <h3 style={{ margin: 0 }}>
              <button
                type="button"
                id={cabecalhoId}
                className="accordion-cabecalho"
                aria-expanded={aberto}
                aria-controls={painelId}
                disabled={item.disabled}
                onClick={() => alternar(item.chave)}
              >
                <span>{item.titulo}</span>
                <span className="accordion-icone" aria-hidden="true">
                  ▾
                </span>
              </button>
            </h3>
            {aberto && (
              <div id={painelId} role="region" aria-labelledby={cabecalhoId} className="accordion-painel">
                {item.conteudo}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
