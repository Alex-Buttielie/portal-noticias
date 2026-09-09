"use client";

import { useEffect, useState } from "react";

// Barra fina de progresso de leitura no topo — `.progresso-leitura*` em
// globals.css. `aria-valuetext` em pt-BR para leitor de tela.
export function ReadingProgress() {
  const [progresso, setProgresso] = useState(0);

  useEffect(() => {
    function atualizar() {
      const altura = document.documentElement.scrollHeight - window.innerHeight;
      setProgresso(altura > 0 ? Math.min(100, Math.max(0, (window.scrollY / altura) * 100)) : 0);
    }
    atualizar();
    window.addEventListener("scroll", atualizar, { passive: true });
    return () => window.removeEventListener("scroll", atualizar);
  }, []);

  const arredondado = Math.round(progresso);

  return (
    <div
      className="progresso-leitura"
      role="progressbar"
      aria-valuenow={arredondado}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuetext={`${arredondado}% lido`}
      aria-label="Progresso de leitura"
    >
      <div className="progresso-leitura__barra" style={{ width: `${progresso}%` }} />
    </div>
  );
}
