// `ads.txt` (IAB) — o Google AdSense exige esse arquivo na raiz do domínio,
// declarando o publisher ID, para aprovar a conta E para servir anúncios
// depois de aprovada. Gerado a partir de `NEXT_PUBLIC_ADSENSE_CLIENT_ID`
// (mesma variável que `AdsSlot`/`AdsScript` já usam) em vez de um arquivo
// estático: nasce correto assim que a variável for preenchida, sem exigir
// outro deploy de código — só a configuração do secret nos 3 ambientes
// (ver `.github/workflows/deploy-prod.yml` e os demais callers).
//
// Formato exigido pelo Google: "google.com, pub-<ID>, DIRECT,
// f08c47fec0942fa0" — o client ID do AdSense vem como "ca-pub-<ID>" (usado
// no `<script data-ad-client>`); o `ads.txt` quer só "pub-<ID>", sem o
// prefixo "ca-".
//
// Sem a variável configurada (conta ainda não aprovada), devolve 404: não
// existe conteúdo válido pra declarar ainda, e um ads.txt vazio/incorreto
// pode atrapalhar a própria revisão de aprovação da conta.

export const revalidate = 3600;

export async function GET() {
  const clientId = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID || "";
  const pubId = clientId.replace(/^ca-/, "");
  if (!pubId.startsWith("pub-")) {
    return new Response("ads.txt ainda não configurado.", { status: 404 });
  }
  const linha = `google.com, ${pubId}, DIRECT, f08c47fec0942fa0\n`;
  return new Response(linha, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
