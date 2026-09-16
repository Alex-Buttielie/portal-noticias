"use client";

import Link from "next/link";

export default function PularParaConteudo() {
  return (
    <Link
      href="#conteudo-principal"
      className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 z-[var(--z-toast)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] px-4 py-2 rounded-md font-medium touch-manipulation min-h-[44px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 motion-reduce:transition-none"
    >
      Pular para o conteúdo principal
    </Link>
  );
}
