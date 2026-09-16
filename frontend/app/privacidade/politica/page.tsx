import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/site";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Política de privacidade",
  description: "Como o Portal de Notícias trata dados pessoais, em conformidade com a LGPD.",
  alternates: { canonical: `${SITE_URL}/privacidade/politica` },
  robots: { index: true, follow: true },
};

const SECOES = [
  {
    valor: "dados",
    titulo: "1. Quais dados coletamos",
    texto:
      "Coletamos dados fornecidos diretamente por você (ex.: e-mail e nome no cadastro, preferências de onboarding) e dados de uso coletados automaticamente, como cookies — somente as categorias que você autorizar (veja a seção 4).",
  },
  {
    valor: "uso",
    titulo: "2. Como usamos seus dados",
    texto:
      "Usamos seus dados para viabilizar sua conta, personalizar sua experiência de leitura (quando você autoriza cookies de personalização), enviar comunicações que você solicitou (ex.: newsletter) e cumprir obrigações legais.",
  },
  {
    valor: "compartilhamento",
    titulo: "3. Compartilhamento de dados",
    texto:
      "Não vendemos dados pessoais. Dados podem ser compartilhados com prestadores de serviço estritamente necessários à operação do site (ex.: envio de e-mail transacional), sob obrigação contratual de confidencialidade.",
  },
  {
    valor: "cookies",
    titulo: "4. Cookies",
    texto: null,
  },
  {
    valor: "direitos",
    titulo: "5. Seus direitos",
    texto:
      "Nos termos da LGPD, você pode solicitar confirmação de tratamento, acesso, correção, anonimização, portabilidade ou eliminação dos seus dados pessoais, entre outros direitos previstos em lei. Para exercer esses direitos, entre em contato pelos canais informados na sua conta.",
  },
  {
    valor: "retencao",
    titulo: "6. Retenção e segurança",
    texto:
      "Mantemos dados pessoais pelo tempo necessário às finalidades descritas nesta política ou pelo prazo exigido por lei, adotando medidas técnicas razoáveis para protegê-los contra acesso não autorizado.",
  },
  {
    valor: "alteracoes",
    titulo: "7. Alterações desta política",
    texto:
      "Esta é uma versão de rascunho e pode mudar substancialmente antes de uma revisão jurídica formal e publicação como versão vigente.",
  },
];

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
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-3xl font-bold leading-tight tracking-tight text-balance text-[var(--cor-texto)]">
            Política de privacidade
          </h1>
          <p className="text-sm leading-relaxed text-[var(--cor-texto-suave)]">
            Esta política descreve, em linhas gerais, como o Portal de Notícias trata dados pessoais de visitantes e
            usuários cadastrados, em conformidade com a Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018).
          </p>
          <Alert variant="warning">
            <AlertTitle>Rascunho</AlertTitle>
            <AlertDescription>
              Este texto ainda não foi revisado por um profissional jurídico. Não deve ser tratado como a versão
              final ou vinculante da política de privacidade do Portal de Notícias.
            </AlertDescription>
          </Alert>
        </CardHeader>
        <CardContent>
          <Accordion type="single" collapsible defaultValue="dados" className="grid gap-2">
            {SECOES.map((secao) => (
              <AccordionItem
                key={secao.valor}
                value={secao.valor}
                className="rounded-lg border border-[var(--cor-borda)] px-4"
              >
                <AccordionTrigger className="text-left text-sm font-semibold text-[var(--cor-texto)]">
                  {secao.titulo}
                </AccordionTrigger>
                <AccordionContent className="text-sm leading-relaxed text-[var(--cor-texto)]">
                  {secao.texto ?? (
                    <p>
                      Usamos cookies essenciais (sempre ativos) e, mediante seu consentimento explícito, cookies de
                      análise e personalização. Você pode revisar e alterar sua escolha a qualquer momento na página{" "}
                      <Link
                        href="/privacidade/preferencias-cookies"
                        className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline"
                      >
                        Preferências de cookies
                      </Link>
                      .
                    </p>
                  )}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </CardContent>
      </Card>
    </div>
  );
}
