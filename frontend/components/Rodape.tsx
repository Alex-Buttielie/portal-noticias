import Link from "next/link";

const SECOES = [
  { href: "/?categoria=pol%C3%ADtica", rotulo: "Política" },
  { href: "/?categoria=economia", rotulo: "Economia" },
  { href: "/?categoria=esportes", rotulo: "Esportes" },
  { href: "/?categoria=tecnologia", rotulo: "Tecnologia" },
  { href: "/radar", rotulo: "Radar" },
  { href: "/comunidade", rotulo: "Comunidade" },
];

const INSTITUCIONAL = [
  { href: "/paginas/termos-de-uso", rotulo: "Termos de uso" },
  { href: "/privacidade/politica", rotulo: "Política de privacidade" },
  { href: "/privacidade/preferencias-cookies", rotulo: "Preferências de cookies" },
  { href: "/paginas/politica-editorial", rotulo: "Política editorial" },
  { href: "/planos", rotulo: "Premium" },
];

const SOCIAIS = [
  { href: "https://x.com", sigla: "X", rotulo: "X (Twitter)" },
  { href: "https://instagram.com", sigla: "IG", rotulo: "Instagram" },
  { href: "https://youtube.com", sigla: "YT", rotulo: "YouTube" },
  { href: "/rss.xml", sigla: "RSS", rotulo: "Feed RSS" },
];

export default function Rodape() {
  const ano = new Date().getFullYear();
  return (
    <footer className="rodape rodape--dark">
      <div className="container">
        <div className="rodape-grid">
          <div className="rodape-marca">
            <Link href="/" className="rodape-logo" aria-label="Portal de Notícias — início">
              <span className="rodape-logo-mark" aria-hidden="true">
                PN
              </span>
              Portal·
            </Link>
            <p>Jornalismo agregado, transparente e em tempo real. Sem rastreadores de terceiros.</p>
            <div className="rodape-social">
              {SOCIAIS.map((s) => (
                <a
                  key={s.rotulo}
                  href={s.href}
                  aria-label={s.rotulo}
                  target={s.href.startsWith("http") ? "_blank" : undefined}
                  rel={s.href.startsWith("http") ? "noopener noreferrer" : undefined}
                >
                  {s.sigla}
                </a>
              ))}
            </div>
          </div>
          <nav aria-label="Seções">
            <h3>Seções</h3>
            {SECOES.map((l) => (
              <Link key={l.rotulo} href={l.href}>
                {l.rotulo}
              </Link>
            ))}
          </nav>
          <nav aria-label="Institucional e privacidade">
            <h3>Institucional</h3>
            {INSTITUCIONAL.map((l) => (
              <Link key={l.rotulo} href={l.href}>
                {l.rotulo}
              </Link>
            ))}
          </nav>
          <nav aria-label="Conta">
            <h3>Conta</h3>
            <Link href="/login">Entrar</Link>
            <Link href="/cadastro">Criar conta</Link>
            <Link href="/minha-conta">Minha conta</Link>
            <Link href="/lista-de-espera">Lista de espera</Link>
          </nav>
        </div>
        <div className="rodape-barra">
          <p>© {ano} Portal de Notícias · Feito com jornalismo e tecnologia</p>
          <p className="rodape-barra-suave">
            <Link href="/privacidade/politica">Privacidade</Link>
            {" · "}
            <Link href="/privacidade/preferencias-cookies">Cookies</Link>
            {" · "}
            <a href="/rss.xml">RSS</a>
          </p>
        </div>
      </div>
    </footer>
  );
}
