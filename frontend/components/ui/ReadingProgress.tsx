"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

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
    <div
      className={cn("fixed top-0 left-0 z-50 h-1 w-full bg-transparent pointer-events-none")}
      role="progressbar"
      aria-valuenow={Math.round(progresso)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Progresso de leitura"
    >
      <div
        className={cn(
          "h-full bg-[var(--cor-primaria)] transition-[width] duration-150 ease-out motion-reduce:transition-none"
        )}
        style={{ width: `${progresso}%` }}
      />
    </div>
  );
}
