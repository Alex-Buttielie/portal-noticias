import { NextRequest, NextResponse } from "next/server";
import {
  caminhoSeguro,
  ehVerdadeiro,
  gerarRequestId,
  normalizarRequestId,
  registrarFalhaApi,
} from "@/lib/observabilidade";

// Proxy mesma-origem `/api/*` -> API Django local. Diferente de `rewrites`
// no next.config (congelado no build), o route handler lê
// API_INTERNAL_URL POR REQUEST: funciona via domínio, IP ou localhost sem
// rebuild (incidente 2026-09-19: acesso direto por IP:porta não passa pelo
// Nginx, então o proxy mora no próprio Next). Default = Django local.
export const dynamic = "force-dynamic";

/**
 * Tempo limite da chamada ao upstream.
 *
 * Antes o `fetch` do proxy não tinha prazo: um Django travado segurava a
 * resposta HTTP (e a memória do body) pelo tempo que o watchdog do
 * orquestrador permitisse, e o navegador só descobria no fim. 30 s é folgado
 * para a ingestão (`POST /api/admin/robos/executar/` responde 202 e roda em
 * background — não precisa de prazo longo) e curto o bastante para o usuário
 * receber um erro em vez de spinner eterno.
 */
const TIMEOUT_PADRAO_MS = 20_000;

/**
 * Teto de body. O envio de credenciamento (`POST /api/credenciamento/...`)
 * carrega foto + documento PDF: sem teto, o `await req.arrayBuffer()` segura o
 * upload inteiro na memória do processo do Next por rota. 16 MB é bem acima do
 * que o backend aceita hoje (Django move arquivo grande para arquivo temporário
 * a partir de 2,5 MB) e ainda limita o pior caso.
 */
const MAX_BODY_BYTES = 16 * 1024 * 1024;

function limitePadrao(): number {
  const bruto = Number(process.env.API_PROXY_TIMEOUT_MS);
  return Number.isFinite(bruto) && bruto > 0 ? bruto : TIMEOUT_PADRAO_MS;
}

function tetoBody(): number {
  const bruto = Number(process.env.API_PROXY_MAX_BODY_BYTES);
  return Number.isFinite(bruto) && bruto > 0 ? bruto : MAX_BODY_BYTES;
}

function destino(req: NextRequest): string {
  const base = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const url = new URL(req.url);
  // Preserva exatamente a barra final e query da URL original — usando
  // pathname evita o bug de perder trailing slash ao remontar via params.
  // Ex: /api/feed/ -> /api/feed/ , /api/feed -> /api/feed (Django 301 se faltar)
  const apiPath = url.pathname.slice(4); // remove "/api" mantendo "/" e resto
  return `${base}/api${apiPath}${url.search}`;
}

/** Só o caminho, sem query: é o que pode virar rótulo de log. */
function rotaSemQuery(req: NextRequest): string {
  return caminhoSeguro(new URL(req.url).pathname);
}

function erroProxy(
  req: NextRequest,
  requestId: string,
  status: number,
  detalhe: string,
  motivo: "timeout" | "conexao" | "corpo",
  inicio: number
): NextResponse {
  registrarFalhaApi({
    origem: "proxy",
    requestId,
    metodo: req.method,
    rota: rotaSemQuery(req),
    status,
    motivo,
    duracaoMs: Date.now() - inicio,
  });
  return NextResponse.json(
    { detail: detalhe, request_id: requestId },
    { status, headers: { "X-Request-ID": requestId } }
  );
}

async function repassar(
  req: NextRequest,
  ctx: { params: { path?: string[] } },
): Promise<NextResponse> {
  // void ctx — assinatura exigida pelo App Router; o caminho vem da URL porque
  // precisa preservar a barra final e a query original.
  void ctx;
  const inicio = Date.now();

  // Critérios 1 e 3: um id seguro é gerado quando o cliente não mandou um id
  // válido, e é o MESMO valor propagado para o Django e devolvido ao browser.
  // O middleware do Django normaliza de novo do lado dele (defesa em profundidade
  // para quem chega sem passar por este proxy).
  const requestId = normalizarRequestId(req.headers.get("X-Request-ID") || gerarRequestId());

  // Teto de body ANTES de ler: `content-length` é só uma dica, então o
  // arrayBuffer também é conferido — um chunked sem o header não escapa do teto.
  const conteudoBruto = req.headers.get("content-length");
  const conteudo = Number(conteudoBruto);
  const teto = tetoBody();
  if (Number.isFinite(conteudo) && conteudo > teto) {
    return erroProxy(
      req,
      requestId,
      413,
      "Arquivo ou formulário maior que o limite aceito (16 MB). Reduza o tamanho e tente novamente.",
      "corpo",
      inicio
    );
  }

  const controller = new AbortController();
  let expirou = false;
  const temporizador = setTimeout(() => {
    expirou = true;
    controller.abort();
  }, limitePadrao());

  let resp: Response;
  try {
    const headers = new Headers(req.headers);
    headers.delete("host");
    headers.delete("connection");
    headers.delete("content-length");
    // Correlação: o Django registra o mesmo id em log, métrica e resposta.
    headers.set("X-Request-ID", requestId);
    // Critérios 5/27: o consentimento técnico viaja COMO VEIO. Este header é
    // booleano e é lido pelo middleware (`X-Technical-Consent`), e é a chave do
    // fail-closed do Sentry no backend: removê-lo aqui faria o evento técnico
    // ser descartado mesmo com consentimento concedido. Ausente, segue ausente
    // — o proxy não amplia consentimento.
    const consentido = req.headers.get("X-Technical-Consent");
    if (ehVerdadeiro(consentido)) headers.set("X-Technical-Consent", "1");
    else headers.delete("X-Technical-Consent");

    const init: RequestInit = {
      method: req.method,
      headers,
      redirect: "manual",
      signal: controller.signal,
    };
    if (req.method !== "GET" && req.method !== "HEAD") {
      const corpo = await req.arrayBuffer();
      if (corpo.byteLength > teto) {
        return erroProxy(
          req,
          requestId,
          413,
          "Arquivo ou formulário maior que o limite aceito (16 MB). Reduza o tamanho e tente novamente.",
          "corpo",
          inicio
        );
      }
      init.body = corpo;
    }
    resp = await fetch(destino(req), init);
  } catch (e) {
    if (expirou) {
      return erroProxy(
        req,
        requestId,
        504,
        "O servidor demorou demais para responder. Tente novamente em alguns instantes.",
        "timeout",
        inicio
      );
    }
    return erroProxy(
      req,
      requestId,
      502,
      "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.",
      "conexao",
      inicio
    );
  } finally {
    clearTimeout(temporizador);
  }

  const saida = new Headers(resp.headers);
  saida.delete("content-encoding");
  saida.delete("transfer-encoding");
  // O header de resposta do Django é a fonte autoritativa do id efetivo; o
  // cliente (`lib/api.ts`) lê daqui. Só normalizamos se o Django não mandou
  // nenhum (resposta de um caminho que não passou pelo middleware).
  const doUpstream = resp.headers.get("X-Request-ID");
  saida.set("X-Request-ID", doUpstream ? normalizarRequestId(doUpstream) : requestId);
  // Desfecho estruturado: request id, desfecho e duração. Só em erro — um log
  // por requisição de sucesso seria ruído e custo sem valor diagnóstico.
  if (!resp.ok && resp.status >= 500) {
    registrarFalhaApi({
      origem: "proxy",
      requestId: saida.get("X-Request-ID"),
      metodo: req.method,
      rota: rotaSemQuery(req),
      status: resp.status,
      motivo: "http",
      duracaoMs: Date.now() - inicio,
    });
  }
  return new NextResponse(resp.body, { status: resp.status, headers: saida });
}

export {
  repassar as GET,
  repassar as POST,
  repassar as PUT,
  repassar as PATCH,
  repassar as DELETE,
  repassar as OPTIONS,
};
