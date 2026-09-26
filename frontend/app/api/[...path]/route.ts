import { NextRequest, NextResponse } from "next/server";

// Proxy mesma-origem `/api/*` -> API Django local. Diferente de `rewrites`
// no next.config (congelado no build), o route handler lê
// API_INTERNAL_URL POR REQUEST: funciona via domínio, IP ou localhost sem
// rebuild (incidente 2026-09-19: acesso direto por IP:porta não passa pelo
// Nginx, então o proxy mora no próprio Next). Default = Django local.
export const dynamic = "force-dynamic";

function destino(req: NextRequest): string {
  const base = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const url = new URL(req.url);
  // Preserva exatamente a barra final e query da URL original — usando
  // pathname evita o bug de perder trailing slash ao remontar via params.
  // Ex: /api/feed/ -> /api/feed/ , /api/feed -> /api/feed (Django 301 se faltar)
  const apiPath = url.pathname.slice(4); // remove "/api" mantendo "/" e resto
  return `${base}/api${apiPath}${url.search}`;
}

// No Next 15 `ctx.params` é um Promise, mas segue deliberadamente NÃO awaited:
// ver `destino()` acima. Reconstruir o path a partir de `params` remontaria
// `/api/feed/` como `/api/feed` e o Django responderia 301, recriando o loop
// 308 (Next) <-> 301 (Django) que o `skipTrailingSlashRedirect` existe para
// evitar. O tipo continua declarado para satisfazer o validador de rota gerado
// pelo Next (.next/types), que confere o segundo argumento do handler.
async function repassar(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  let resp: Response;
  try {
    const headers = new Headers(req.headers);
    headers.delete("host");
    headers.delete("connection");
    headers.delete("content-length");
    const init: RequestInit = { method: req.method, headers, redirect: "manual" };
    if (req.method !== "GET" && req.method !== "HEAD") {
      init.body = await req.arrayBuffer();
    }
    resp = await fetch(destino(req), init);
  } catch (e) {
    console.error("[api-proxy] fetch falhou", e);
    return NextResponse.json(
      { detail: "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente." },
      { status: 502 },
    );
  }
  const saida = new Headers(resp.headers);
  saida.delete("content-encoding");
  saida.delete("transfer-encoding");
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
