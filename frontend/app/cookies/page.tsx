import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Cookies — ${SITE_NAME}`, description: `Política de cookies do ${SITE_NAME}.` };
export default function Page() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6"><div className="hud-line mb-4" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Cookies</h1><p className="text-sm text-[var(--cor-texto-suave)]">Você controla tudo pelo banner. Se estiver logado, suas preferências de analytics e personalização ficam salvas na sua conta.</p></div>
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardContent className="prose max-w-none p-5 prose-p:text-[var(--cor-texto-suave)] prose-headings:text-[var(--cor-texto)]">
          <h2>Essenciais</h2>
          <p>Sessão e segurança — sempre ativos. Não são uma escolha sua.</p>
          <h2>Analytics</h2>
          <p>Medição de audiência — só com seu consentimento, separado das outras categorias.</p>
          <h2>Personalização</h2>
          <p>Feed “para você” e publicidade de terceiros, como AdSense — só com consentimento.</p>
          <h2>Diagnóstico técnico</h2>
          <p>
            Erros de navegação e medidas de desempenho do portal, usados para encontrar e corrigir
            falhas. É uma categoria separada de analytics: não mede audiência, não mede o que você lê
            e não é ligada junto com as outras. Padrão é <strong>desligada</strong> — sem sua
            autorização, nenhum evento técnico sai do navegador.
          </p>
          <p>
            Esse diagnóstico não envia token, e-mail, IP completo, conteúdo de páginas nem a parte
            da URL que você digitou. Cada requisição usa um identificador técnico anônimo, gerado
            localmente, que existe para correlacionar o erro na sua tela com o registro do servidor.
          </p>
          <p>
            Você liga e desliga cada categoria em{" "}
            <Link href="/privacidade/preferencias-cookies">preferências de cookies</Link>, a qualquer
            momento.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
