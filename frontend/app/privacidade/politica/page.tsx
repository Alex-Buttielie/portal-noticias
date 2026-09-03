import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Política de privacidade",
  description: "Como o Portal de Notícias trata dados pessoais, em conformidade com a LGPD.",
  alternates: { canonical: `${SITE_URL}/privacidade/politica` },
  robots: { index: true, follow: true },
};

/**
 * RASCUNHO funcional (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo B — Não-objetivos: "Não
 * escrever a versão final/jurídica da política de privacidade"). Texto
 * genérico em português, não revisado por jurídico — task-plan.md,
 * "Suposições assumidas". Precisa de revisão jurídica antes de uso em
 * produção real.
 */
export default function PaginaPoliticaPrivacidade() {
  return (
    <div>
      <div className="mensagem-erro" role="note">
        <strong>Rascunho:</strong> este texto ainda não foi revisado por um profissional
        jurídico. Não deve ser tratado como a versão final/vinculante da política de
        privacidade do Portal de Notícias.
      </div>

      <h1>Política de privacidade</h1>
      <p className="texto-suave">
        Esta política descreve, em linhas gerais, como o Portal de Notícias trata dados
        pessoais de visitantes e usuários cadastrados, em conformidade com a Lei Geral de
        Proteção de Dados (LGPD — Lei nº 13.709/2018).
      </p>

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>1. Quais dados coletamos</h2>
      <p>
        Coletamos dados fornecidos diretamente por você (ex.: e-mail e nome no cadastro,
        preferências de onboarding) e dados de uso coletados automaticamente, como cookies —
        somente as categorias que você autorizar (veja a seção 4).
      </p>

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>2. Como usamos seus dados</h2>
      <p>
        Usamos seus dados para viabilizar sua conta, personalizar sua experiência de leitura
        (quando você autoriza cookies de personalização), enviar comunicações que você
        solicitou (ex.: newsletter) e cumprir obrigações legais.
      </p>

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>3. Compartilhamento de dados</h2>
      <p>
        Não vendemos dados pessoais. Dados podem ser compartilhados com prestadores de
        serviço estritamente necessários à operação do site (ex.: envio de e-mail
        transacional), sob obrigação contratual de confidencialidade.
      </p>

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>4. Cookies</h2>
      <p>
        Usamos cookies essenciais (sempre ativos) e, mediante seu consentimento explícito,
        cookies de análise e personalização. Você pode revisar e alterar sua escolha a
        qualquer momento na página{" "}
        <Link href="/privacidade/preferencias-cookies">Preferências de cookies</Link>.
      </p>

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>5. Seus direitos</h2>
      <p>
        Nos termos da LGPD, você pode solicitar confirmação de tratamento, acesso,
        correção, anonimização, portabilidade ou eliminação dos seus dados pessoais, entre
        outros direitos previstos em lei. Para exercer esses direitos, entre em contato pelos
        canais informados na sua conta.
      </p>

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>6. Retenção e segurança</h2>
      <p>
        Mantemos dados pessoais pelo tempo necessário às finalidades descritas nesta
        política ou pelo prazo exigido por lei, adotando medidas técnicas razoáveis para
        protegê-los contra acesso não autorizado.
      </p>

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>7. Alterações desta política</h2>
      <p>
        Esta é uma versão de rascunho e pode mudar substancialmente antes de uma revisão
        jurídica formal e publicação como versão vigente.
      </p>
    </div>
  );
}
