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
    window.addEventListener("resize", atualizar);
    return () => {
      window.removeEventListener("scroll", atualizar);
      window.removeEventListener("resize", atualizar);
    };
  }, []);

  return (
    <div
      className={cn("pointer-events-none fixed inset-x-0 top-0 z-50 h-1 bg-transparent")}
      role="progressbar"
      aria-valuenow={Math.round(progresso)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Progresso de leitura"
    >
      <div
        className={cn("h-full w-full origin-left bg-[var(--cor-primaria)] motion-reduce:transition-none")}
        style={{ transform: `scaleX(${progresso / 100})` }}
      />
    </div>
  );
}
