import Link from "next/link";

export default function Rodape() {
  const ano = new Date().getFullYear();
  return (
    <footer className="rodape rodape--dark">
      <div className="container">
        <div className="rodape-grid">
          <div className="rodape-marca">
            <span className="rodape-logo">
              <span className="rodape-logo-mark">BRD</span> Portal de Notícias
            </span>
            <p>Jornalismo independente, apuração transparente e feed em tempo real.</p>
            <div className="rodape-social" aria-label="Redes sociais">
              <a href="#" aria-label="Facebook">f</a>
              <a href="#" aria-label="Instagram">◎</a>
              <a href="#" aria-label="YouTube">▶</a>
              <a href="#" aria-label="X">𝕏</a>
            </div>
          </div>
          <nav aria-label="Editorias">
            <h3>Categorias</h3>
            <Link href="/?categoria=pol%C3%ADtica">Política</Link>
            <Link href="/?categoria=economia">Economia</Link>
            <Link href="/?categoria=esportes">Esportes</Link>
            <Link href="/?categoria=tecnologia">Tecnologia</Link>
            <Link href="/?categoria=mundo">Mundo</Link>
          </nav>
          <nav aria-label="Institucional">
            <h3>Institucional</h3>
            <Link href="/paginas/termos-de-uso">Termos de uso</Link>
            <Link href="/privacidade/politica">Política de privacidade</Link>
            <Link href="/privacidade/preferencias-cookies">Preferências de cookies</Link>
            <Link href="/paginas/politica-editorial">Política editorial</Link>
            <Link href="/planos">Assine Premium</Link>
          </nav>
          <nav aria-label="Descubra">
            <h3>Descubra</h3>
            <Link href="/comunidade">Comunidade</Link>
            <Link href="/radar">Radar de tendências</Link>
            <Link href="/jornalista/status">Seja jornalista</Link>
            <Link href="/empresa">Para empresas</Link>
            <a href="/rss.xml">RSS</a>
          </nav>
        </div>
        <div className="rodape-barra">
          <p>© {ano} Portal de Notícias. Todos os direitos reservados.</p>
          <p className="rodape-barra-suave">Feito com jornalismo e tecnologia — design inspirado em Hugo Gloss × Metrópoles.</p>
        </div>
      </div>
    </footer>
  );
}
