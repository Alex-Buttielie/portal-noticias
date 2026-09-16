import Link from "next/link";
import { FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <div className="container flex min-h-[50vh] flex-col items-center justify-center py-16">
      <div className="estado-vazio flex max-w-[560px] flex-col items-center gap-4 rounded-2xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-6 py-10 text-center shadow-sm sm:px-10 sm:py-12">
        <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]">
          <FileQuestion className="h-6 w-6" aria-hidden="true" />
        </span>
        <p className="estado-vazio__titulo m-0 font-[var(--fonte-titulo)] text-xl font-bold tracking-tight text-[var(--cor-texto)] sm:text-2xl">
          Você chegou a uma página que não existe
        </p>
        <p className="estado-vazio__descricao m-0 max-w-[40ch] text-sm leading-6 text-[var(--cor-texto-suave)]">
          Confira o endereço ou volte ao início para acompanhar as últimas notícias.
        </p>
        <Link
          href="/"
          className="botao botao--primaria botao--medio inline-flex h-11 items-center justify-center rounded-full bg-[var(--cor-primaria)] px-6 text-sm font-semibold text-white no-underline transition-colors hover:bg-[var(--cor-primaria-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 motion-reduce:transition-none"
        >
          Voltar ao início
        </Link>
      </div>
    </div>
  );
}
