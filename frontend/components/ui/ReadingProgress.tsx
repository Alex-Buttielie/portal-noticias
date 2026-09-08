"use client";

import { useEffect, useState } from "react";

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

  return (
    <div className="progresso-leitura" role="progressbar" aria-valuenow={Math.round(progresso)} aria-valuemin={0} aria-valuemax={100} aria-label="Progresso de leitura">
      <div className="progresso-leitura__barra" style={{ width: `${progresso}%` }} />
    </div>
  );
}
