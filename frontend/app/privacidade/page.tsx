import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Privacidade — ${SITE_NAME}`, description: `Política de privacidade do ${SITE_NAME} — LGPD.` };
export default function Page() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6"><div className="hud-line mb-4" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Privacidade</h1><p className="text-sm text-[var(--cor-texto-suave)]">LGPD • Banner de consentimento preservado.</p></div>
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardContent className="prose max-w-none p-5 prose-p:text-[var(--cor-texto-suave)] prose-headings:text-[var(--cor-texto)]">
          <h2>Dados que coletamos</h2>
          <p>Apenas o necessário para operar o portal. Cookies analíticos só com consentimento.</p>
          <h2>Telemetria técnica é uma categoria separada</h2>
          <p>
            A medição de audiência (analytics) e o diagnóstico técnico são categorias
            independentes, com interruptores separados em{" "}
            <a href="/privacidade/preferencias-cookies">preferências de cookies</a>. O diagnóstico
            técnico existe para que a equipe consiga encontrar e corrigir falhas do portal: quando
            está autorizado, erros de navegação e medidas de desempenho podem ser enviados a um
            serviço de diagnóstico. Essa telemetria <strong>não</strong> registra o que você lê,
            busca ou clica, e não é ativada junto com o consentimento de analytics.
          </p>
          <p>
            Quando o diagnóstico técnico está desligado — o padrão — o portal funciona por
            completo e nenhum evento de erro ou desempenho sai do seu navegador. A escolha é
            respeitada de forma fechada: sem autorização explícita, nada é enviado.
          </p>
          <h2>O que a telemetria técnica não leva</h2>
          <p>
            Não são enviados token de sessão, e-mail, endereço IP completo, conteúdo de páginas
            nem partes da URL que você digitou (busca, convites, parâmetros). Cada requisição
            carrega um identificador técnico gerado no seu navegador, sem relação com a sua
            identidade, usado para correlacionar o erro que você vê com os registros do servidor.
          </p>
          <h2>Seus direitos</h2>
          <p>Acesso, correção e exclusão via Contato. Você pode mudar seu consentimento a qualquer momento.</p>
          <h2>Retenção</h2>
          <p>Dados mantidos enquanto a conta existir ou por obrigação legal.</p>
        </CardContent>
      </Card>
    </div>
  );
}
