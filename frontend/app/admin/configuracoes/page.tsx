import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { SITE_NAME, SITE_DESCRIPTION, SITE_URL, IMAGEM_OG_PADRAO } from "@/lib/site";
import { API_BASE_URL } from "@/lib/api";
import { Globe, Mail, FileText, Settings, ExternalLink, Info } from "lucide-react";

export const metadata = { title: "Configurações — Admin" };

const ENVS = [
  { variavel: "NEXT_PUBLIC_SITE_URL", valor: SITE_URL, padrao: "http://localhost:3000", onde: "frontend/.env — NEXT_PUBLIC_SITE_URL", nota: "Usado em canonical / OG / sitemap" },
  { variavel: "NEXT_PUBLIC_API_BASE_URL", valor: API_BASE_URL, padrao: "http://localhost:8000", onde: "frontend/.env — NEXT_PUBLIC_API_BASE_URL", nota: "Base da API consumida pelo frontend" },
  { variavel: "FRONTEND_BASE_URL", valor: SITE_URL, padrao: "http://localhost:3000", onde: "backend/.env — FRONTEND_BASE_URL", nota: "Links de e-mail (verificação / reset) e CORS" },
  { variavel: "DJANGO_EMAIL_BACKEND", valor: "django.core.mail.backends.console.EmailBackend", padrao: "console", onde: "backend/.env — DJANGO_EMAIL_BACKEND", nota: "Dev: console · Prod: provedor transacional" },
  { variavel: "TERMOS_VERSAO_ATUAL", valor: "1.0", padrao: "1.0", onde: "backend/.env — TERMOS_VERSAO_ATUAL", nota: "Versão vigente aceita no cadastro (LGPD)" },
  { variavel: "DJANGO_DEFAULT_FROM_EMAIL", valor: "no-reply@brdportalnoticias.local", padrao: "no-reply@brdportalnoticias.local", onde: "backend/.env — DJANGO_DEFAULT_FROM_EMAIL", nota: "Remetente padrão dos e-mails" },
];

function statusEnv(v: string, padrao: string) {
  const isPadrao = v === padrao || v.includes("localhost") || v.includes("console") || v.includes("local");
  return isPadrao ? { label: "alerta", cls: "border-[var(--cor-alerta)] text-[var(--cor-alerta)]" } : { label: "ok", cls: "border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]" };
}

const PAGINAS = [
  { slug: "termos", titulo: "Termos de uso", href: "/paginas/termos" },
  { slug: "privacidade", titulo: "Política de privacidade", href: "/paginas/privacidade" },
  { slug: "sobre", titulo: "Sobre", href: "/paginas/sobre" },
  { slug: "cookies", titulo: "Política de cookies", href: "/paginas/cookies" },
];

export default function Page() {
  return (
    <div className="space-y-4">
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Settings className="h-5 w-5 text-[var(--cor-primaria)]" /> Configurações gerais</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">Tudo que não tem módulo dedicado — identidade, envs, páginas editoriais e e-mail/onboarding. Valores de env são somente leitura aqui: edite via <code className="rounded bg-[var(--cor-fundo-elevado)] px-1 py-0.5 font-mono text-xs">.env</code>.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4">
            <p className="flex items-center gap-2 text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]"><Globe className="h-3.5 w-3.5" /> IDENTIDADE DO SITE — lib/site.ts</p>
            <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
              <div><p className="text-xs text-[var(--cor-texto-suave)]">SITE_NAME</p><p className="font-medium text-[var(--cor-texto)]">{SITE_NAME}</p></div>
              <div><p className="text-xs text-[var(--cor-texto-suave)]">SITE_URL</p><p className="font-mono text-xs text-[var(--cor-texto)] break-all">{SITE_URL}</p></div>
              <div className="md:col-span-2"><p className="text-xs text-[var(--cor-texto-suave)]">SITE_DESCRIPTION</p><p className="text-xs leading-relaxed text-[var(--cor-texto-suave)]">{SITE_DESCRIPTION}</p></div>
              <div className="md:col-span-2"><p className="text-xs text-[var(--cor-texto-suave)]">IMAGEM_OG_PADRAO</p><p className="font-mono text-xs text-[var(--cor-texto-suave)] break-all">{IMAGEM_OG_PADRAO}</p></div>
            </div>
            <p className="mt-3 flex items-center gap-1.5 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2.5 py-2 text-xs text-[var(--cor-texto-suave)]"><Info className="h-3.5 w-3.5 shrink-0" /> Editar via env <code className="font-mono">NEXT_PUBLIC_SITE_URL</code> — sem deploy de código.</p>
          </div>

          <div>
            <p className="text-sm font-semibold text-[var(--cor-texto)]">Variáveis configuráveis (informativo)</p>
            <p className="text-xs text-[var(--cor-texto-suave)]">Status <span className="font-medium text-[var(--cor-sucesso)]">ok</span> = valor próprio de produção · <span className="font-medium text-[var(--cor-alerta)]">alerta</span> = fallback local/dev.</p>
            <div className="mt-3 overflow-x-auto rounded-[var(--raio-md)] border border-[var(--cor-borda)]">
              <table className="w-full min-w-[640px] text-sm">
                <thead><tr className="border-b border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-left text-xs text-[var(--cor-texto-suave)]"><th className="px-3 py-2 font-medium">Variável</th><th className="px-3 py-2 font-medium">Valor atual</th><th className="px-3 py-2 font-medium">Status</th><th className="px-3 py-2 font-medium">Onde editar</th></tr></thead>
                <tbody>
                  {ENVS.map((e) => {
                    const s = statusEnv(e.valor, e.padrao);
                    return (
                      <tr key={e.variavel} className="border-b border-[var(--cor-borda)] last:border-0">
                        <td className="px-3 py-2 font-mono text-xs font-medium text-[var(--cor-texto)]">{e.variavel}<p className="font-sans text-[10px] font-normal text-[var(--cor-texto-suave)]">{e.nota}</p></td>
                        <td className="max-w-[260px] truncate px-3 py-2 font-mono text-xs text-[var(--cor-texto-suave)]">{e.valor}</td>
                        <td className="px-3 py-2"><Badge variant="outline" className={s.cls}>{s.label}</Badge></td>
                        <td className="px-3 py-2 font-mono text-[10px] text-[var(--cor-texto-suave)]">{e.onde}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <Separator className="bg-[var(--cor-borda)]" />

          <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-[var(--cor-texto)]"><FileText className="h-4 w-4 text-[var(--cor-primaria)]" /> Conteúdo editorial</p>
            <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Páginas estáticas servidas por <code className="font-mono">/paginas/[slug]</code> via <code className="font-mono">/api/moderacao/paginas/{"{slug}"}/</code>. Sem CRUD dedicado na Central — placeholder com links.</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {PAGINAS.map((p) => (
                <a key={p.slug} href={p.href} className="flex items-center justify-between rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2.5 text-sm font-medium text-[var(--cor-texto)] hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)] transition-colors">
                  <span>{p.titulo}<span className="ml-2 font-mono text-xs font-normal text-[var(--cor-texto-suave)]">/{p.slug}</span></span><ExternalLink className="h-3.5 w-3.5 text-[var(--cor-texto-suave)]" />
                </a>
              ))}
            </div>
            <p className="mt-3 text-xs text-[var(--cor-texto-suave)]">Para editar, use a API de páginas editoriais ou adicione CRUD em <code className="font-mono">/admin/paginas/[slug]</code> quando necessário.</p>
          </div>

          <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-[var(--cor-texto)]"><Mail className="h-4 w-4 text-[var(--cor-primaria)]" /> E-mail / Onboarding</p>
            <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
              <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3"><p className="text-xs text-[var(--cor-texto-suave)]">EMAIL_BACKEND</p><p className="font-mono text-xs text-[var(--cor-texto)]">console (dev)</p><p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Envie via provedor real definindo <code className="font-mono">DJANGO_EMAIL_BACKEND</code> em produção.</p><Badge variant="outline" className="mt-2 border-[var(--cor-alerta)] text-[var(--cor-alerta)]">alerta — dev</Badge></div>
              <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3"><p className="text-xs text-[var(--cor-texto-suave)]">TERMOS_VERSAO_ATUAL</p><p className="font-mono text-xs text-[var(--cor-texto)]">1.0</p><p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Versão exigida no cadastro; gravada em <code className="font-mono">User.consentimento_versao_termos</code>. Altere via <code className="font-mono">TERMOS_VERSAO_ATUAL</code>.</p><Badge variant="outline" className="mt-2 border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]">ok</Badge></div>
            </div>
            <p className="mt-3 text-xs text-[var(--cor-texto-suave)]">Módulos dedicados: <a href="/admin/planos" className="underline hover:text-[var(--cor-primaria)]">Planos</a> · <a href="/admin/limites" className="underline hover:text-[var(--cor-primaria)]">Limites</a> · <a href="/admin/robos" className="underline hover:text-[var(--cor-primaria)]">Robôs (17 campos)</a> — 100% configuráveis pela Central.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
