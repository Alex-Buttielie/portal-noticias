import Link from "next/link";
export function Rodape() {
  return (
    <footer className="border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
      <div className="hud-line" />
      <div className="mx-auto max-w-[1280px] px-4 py-8 md:px-6">
        <div className="grid gap-6 md:grid-cols-4">
          <div className="bento p-4">
            <div className="mb-2 flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-md text-xs font-bold text-[var(--cor-texto-invertido)]" style={{ background: "var(--gradiente-marca)" }}>◈</span>
              <span className="text-sm font-bold text-[var(--cor-texto)]">Portal de Notícias</span>
            </div>
            <p className="text-sm leading-relaxed text-[var(--cor-texto-suave)]">Toda a informação que importa, organizada em um só lugar.</p>
          </div>
          <nav aria-label="Institucional" className="space-y-2">
            <h2 className="text-sm font-semibold text-[var(--cor-texto)]">Institucional</h2>
            <ul className="space-y-1 text-sm text-[var(--cor-texto-suave)]">
              <li><Link href="/empresa" className="hover:text-[var(--cor-texto)] hover:underline">Empresa</Link></li>
              <li><Link href="/paginas/sobre" className="hover:text-[var(--cor-texto)] hover:underline">Sobre</Link></li>
              <li><Link href="/planos" className="hover:text-[var(--cor-texto)] hover:underline">Planos</Link></li>
            </ul>
          </nav>
          <nav aria-label="Categorias" className="space-y-2">
            <h2 className="text-sm font-semibold text-[var(--cor-texto)]">Categorias</h2>
            <ul className="space-y-1 text-sm text-[var(--cor-texto-suave)]">
              <li><Link href="/?categoria=politica" className="hover:text-[var(--cor-texto)] hover:underline">Política</Link></li>
              <li><Link href="/?categoria=economia" className="hover:text-[var(--cor-texto)] hover:underline">Economia</Link></li>
              <li><Link href="/?categoria=tecnologia" className="hover:text-[var(--cor-texto)] hover:underline">Tecnologia</Link></li>
              <li><Link href="/radar" className="hover:text-[var(--cor-texto)] hover:underline">Radar</Link></li>
            </ul>
          </nav>
          <nav aria-label="Legal" className="space-y-2">
            <h2 className="text-sm font-semibold text-[var(--cor-texto)]">Legal</h2>
            <ul className="space-y-1 text-sm text-[var(--cor-texto-suave)]">
              <li><Link href="/privacidade" className="hover:text-[var(--cor-texto)] hover:underline">Privacidade</Link></li>
              <li><Link href="/privacidade/cookies" className="hover:text-[var(--cor-texto)] hover:underline">Cookies</Link></li>
              <li><Link href="/privacidade/termos" className="hover:text-[var(--cor-texto)] hover:underline">Termos</Link></li>
            </ul>
          </nav>
        </div>
        <div className="mt-6 flex flex-col gap-2 border-t border-[var(--cor-borda)] pt-4 text-xs text-[var(--cor-texto-suave)] md:flex-row md:items-center md:justify-between">
          <span>© {new Date().getFullYear()} Portal de Notícias. Todos os direitos reservados.</span>
          <span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[var(--cor-sinal)]" aria-hidden /> Feito para leitura confortável</span>
        </div>
      </div>
    </footer>
  );
}
