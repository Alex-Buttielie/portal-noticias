import Link from "next/link";

export default function Rodape() {
  const ano = new Date().getFullYear();
  return (
    <footer className="base">
      <div className="container base__linhas">
        <div className="base__marca">
          <Link href="/" className="topo__marca" aria-label="Portal de Notícias — início">
            <span className="topo__orbe" aria-hidden="true" />
            <span className="topo__nome">
              Portal<em>·</em>
            </span>
          </Link>
          <p>Jornalismo agregado, transparente e em tempo real.</p>
        </div>
        <nav className="base__links" aria-label="Institucional">
          <Link href="/paginas/termos-de-uso">Termos</Link>
          <Link href="/privacidade/politica">Privacidade</Link>
          <Link href="/privacidade/preferencias-cookies">Cookies</Link>
          <Link href="/paginas/politica-editorial">Editorial</Link>
          <Link href="/planos">Premium</Link>
          <a href="/rss.xml">RSS</a>
        </nav>
        <p className="base__fino">
          © {ano} Portal de Notícias · Feito com jornalismo e tecnologia
        </p>
      </div>
    </footer>
  );
}
