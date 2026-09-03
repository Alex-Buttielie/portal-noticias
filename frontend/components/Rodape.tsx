import Link from "next/link";

/**
 * Rodapé global — hoje existe principalmente para hospedar os links exigidos
 * pelo escopo de privacidade/LGPD desta run (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, critério de aceite 4 do
 * task-plan.md: página de preferências de cookies "acessível a qualquer
 * momento (ex.: rodapé)"). Server component simples, sem estado.
 */
export default function Rodape() {
  const ano = new Date().getFullYear();
  return (
    <footer className="rodape">
      <div className="container rodape-conteudo">
        <nav className="rodape-links" aria-label="Links de privacidade">
          <Link href="/paginas/termos-de-uso">Termos de uso</Link>
          <Link href="/privacidade/politica">Política de privacidade</Link>
          <Link href="/privacidade/preferencias-cookies">Preferências de cookies</Link>
          <Link href="/paginas/politica-editorial">Política editorial</Link>
          <a href="/rss.xml">RSS</a>
        </nav>
        <p className="texto-suave">© {ano} Portal de Notícias.</p>
      </div>
    </footer>
  );
}
