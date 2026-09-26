import type { ReactNode } from "react";
import { urlSeguraParaLink, hostnameSeguro } from "@/lib/url-segura";

/**
 * Link para uma FONTE EXTERNA (RSS, gateway) com allowlist de esquema.
 *
 * Antes do hardening (P0-10, eixo 1) os pontos de uso faziam
 * `<a href={fonte.url_fonte_original}>` direto. `url_fonte_original`
 * vem do XML do feed — conteúdo de terceiro, não confiável. Um feed com
 * `<link>javascript:alert(document.cookie)</link>` virava XSS armazenado
 * no clique de qualquer leitor. Isto é o mesmo padrão que o
 * `NoScript` de OWASP exige para URLTERS: allowlist de esquema, validada
 * no ponto de uso, com fallback INERTE (não a URL original).
 *
 * Se a URL for recusada, renderiza `<span>` com o mesmo conteúdo visual:
 * o leitor vê que existe uma fonte, mas não há destination clicável.
 * Nunca devolvemos a URL original como fallback — isso seria o mesmo XSS
 * com outro nome.
 */
export function LinkFonte({
  url,
  children,
  className,
  /** Prefixo visual (ex.: "↗ "). */
  prefixo,
}: {
  url: string | null | undefined;
  children: ReactNode;
  className?: string;
  prefixo?: string;
}) {
  const segura = urlSeguraParaLink(url);
  const conteudo = (
    <>
      {prefixo ? <span aria-hidden>{prefixo}</span> : null}
      {children}
    </>
  );
  if (!segura) {
    return (
      <span className={className} title="Link da fonte descartado: esquema de URL não permitido">
        {conteudo}
      </span>
    );
  }
  return (
    <a
      href={segura}
      target="_blank"
      // noopener+noreferrer: a página de destino não ganha acesso a
      // `window.opener` (reverse tabnabbing) nem ao Referer.
      rel="noopener noreferrer nofollow"
      className={className}
    >
      {conteudo}
    </a>
  );
}

/** Hostname da fonte, ou string vazia se a URL for descartada. */
export function HostnameFonte({ url }: { url: string | null | undefined }) {
  const host = hostnameSeguro(url);
  if (!host) return <span title="Origem indisponível">origem desconhecida</span>;
  return <>{host}</>;
}

export default LinkFonte;
