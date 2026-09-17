"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Check, X, Crown, ShieldCheck, Sparkles, Zap, Newspaper, Bell, Archive, Users, HelpCircle } from "lucide-react";
import { obterPlanos, assinarPlano, type Plano } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { toast } from "sonner";
import { AdsSlot } from "@/components/AdsSlot";

const FALLBACK: Plano[] = [
  { id: 1, nome: "Free", preco: "0.00", duracao_dias: 0, ativo: true },
  { id: 2, nome: "Premium", preco: "29.90", duracao_dias: 30, ativo: true },
];

const PREMIUM_BENEFICIOS = [
  { icon: Newspaper, text: "Feed sem anúncios", sub: "leitura limpa, sem banners" },
  { icon: Zap, text: "Radar ilimitado", sub: "tendências e evolução completas" },
  { icon: Bell, text: "Alertas personalizados", sub: "siga temas e receba no seu ritmo" },
  { icon: Users, text: "Acesso à Central", sub: "comunidade e vozes credenciadas" },
  { icon: Archive, text: "Histórico completo", sub: "arquivo liberado, sem limite de dias" },
  { icon: ShieldCheck, text: "Suporte prioritário", sub: "resposta mais rápida da equipe" },
];

const FREE_BENEFICIOS = ["Feed com anúncios", "20 matérias por dia", "Radar: 3 consultas/dia", "1 alerta", "7 dias de histórico"];

const COMPARATIVO: { recurso: string; free: string; premium: string; chave?: string }[] = [
  { recurso: "Feed sem anúncios", free: "—", premium: "✓", chave: "feed_sem_anuncios" },
  { recurso: "Itens por dia", free: "20", premium: "ilimitado", chave: "feed_max_itens" },
  { recurso: "Radar", free: "3/dia", premium: "ilimitado", chave: "radar_credito" },
  { recurso: "Alertas personalizados", free: "1", premium: "ilimitado", chave: "alertas_max" },
  { recurso: "Histórico e arquivo", free: "7 dias", premium: "completo", chave: "historico_dias" },
  { recurso: "Suporte", free: "padrão", premium: "prioritário" },
  { recurso: "Acesso à Central", free: "—", premium: "✓" },
];

const FAQ = [
  { q: "Posso cancelar quando quiser?", a: "Sim. O cancelamento é imediato e você mantém o acesso até o fim do período pago." },
  { q: "O que muda no dia a dia?", a: "Sem anúncios, mais matérias por dia, radar e alertas sem limite e arquivo completo — sem jargão, só mais conteúdo." },
  { q: "Preciso pagar agora?", a: "Você escolhe o plano e confirma. Se não estiver logado, pedimos login antes." },
];

export default function Page() {
  const router = useRouter();
  const { token } = useAuth();
  const [planos, setPlanos] = useState<Plano[]>([]);
  const [sel, setSel] = useState<Plano | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    obterPlanos().then((p) => setPlanos(p?.length ? p : FALLBACK)).catch(() => setPlanos(FALLBACK));
  }, []);

  const premium = planos.find((p) => p.nome.toLowerCase().includes("premium")) ?? planos[1] ?? FALLBACK[1];
  const free = planos.find((p) => p.nome.toLowerCase().includes("free")) ?? planos[0] ?? FALLBACK[0];

  function escolher(p: Plano) { setSel(p); setErro(null); setOk(false); setOpen(true); }

  async function confirmar() {
    if (!sel) return;
    if (!token) { setOpen(false); router.push("/login"); return; }
    setLoading(true); setErro(null);
    try { await assinarPlano(token, sel.id); setOk(true); toast.success("Assinatura confirmada"); }
    catch (e: unknown) { const m = e instanceof Error ? e.message : "Não foi possível assinar."; setErro(m); toast.error(m); }
    finally { setLoading(false); }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-6">
      <div className="hud-line" aria-hidden />
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6">
        <p className="text-xs font-semibold tracking-widest text-[var(--cor-primaria)]">PLANOS</p>
        <h1 className="mt-1 text-3xl font-bold text-[var(--cor-texto)]">Escolha como você quer ler</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--cor-texto-suave)]">Sem jargão: conta gratuita para começar. <strong className="font-semibold text-[var(--cor-texto)]">Premium</strong> tira anúncios, libera radar e alertas sem limite, arquivo completo e suporte prioritário.</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]"><Badge variant="outline" className="border-[var(--cor-borda)]"><Users className="mr-1 h-3 w-3" /> +12.000 assinantes</Badge><span>·</span><span>Cancele quando quiser</span></div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">{free.nome}<Badge variant="outline" className="border-[var(--cor-borda)]">grátis</Badge></CardTitle>
            <CardDescription className="text-[var(--cor-texto-suave)]"><span className="text-2xl font-bold text-[var(--cor-texto)]">R$ {free.preco}</span> <span className="text-xs">· sem cobrança</span></CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-2 text-sm text-[var(--cor-texto)]">{FREE_BENEFICIOS.map((b) => <li key={b} className="flex gap-2"><span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--cor-borda)]"><X className="h-3.5 w-3.5 text-[var(--cor-texto-suave)]" /></span>{b}</li>)}</ul>
            <Button variant="outline" onClick={() => escolher(free)} className="w-full min-h-[44px] border-[var(--cor-borda)]">Continuar no Free</Button>
            <p className="text-center text-xs text-[var(--cor-texto-suave)]">Sem cartão. Comece agora.</p>
          </CardContent>
        </Card>

        <Card className="bento relative overflow-hidden border-[var(--cor-neon-violeta)] bg-[var(--cor-fundo-card)] shadow-[0_0_0_1px_var(--cor-neon-violeta),0_8px_24px_rgba(124,58,237,0.15)]">
          <div className="absolute inset-x-0 top-0 h-1 bg-[var(--gradiente-marca)]" aria-hidden />
          <Badge className="absolute right-4 top-4 bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]">Mais popular</Badge>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Crown className="h-5 w-5 text-[var(--cor-premium)]" /> {premium.nome}</CardTitle>
            <CardDescription className="text-[var(--cor-texto-suave)]"><span className="text-2xl font-bold text-[var(--cor-texto)]">R$ {premium.preco}</span> <span className="text-xs">/ {premium.duracao_dias || 30} dias</span></CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-2.5 text-sm text-[var(--cor-texto)]">{PREMIUM_BENEFICIOS.map(({ icon: Icon, text, sub }) => <li key={text} className="flex gap-2.5"><span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--cor-premium-suave)] text-[var(--cor-premium)]"><Check className="h-3.5 w-3.5" /></span><span><span className="font-medium">{text}</span> <span className="text-[var(--cor-texto-suave)]">— {sub}</span></span></li>)}</ul>
            <Button onClick={() => escolher(premium)} className="w-full min-h-[44px] bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-premium-hover)]"><Crown className="mr-2 h-4 w-4" /> Assinar premium</Button>
            <p className="text-center text-xs text-[var(--cor-texto-suave)]">Cobrança recorrente · cancele quando quiser</p>
          </CardContent>
        </Card>
      </div>

      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader><CardTitle className="text-base">Comparativo</CardTitle><CardDescription>O que muda entre Free e Premium — sem termos técnicos.</CardDescription></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead><tr className="border-b border-[var(--cor-borda)] text-left text-xs text-[var(--cor-texto-suave)]"><th className="py-2 font-medium">Recurso</th><th className="py-2 text-center font-medium">Free</th><th className="py-2 text-center font-medium">Premium</th></tr></thead>
            <tbody>
              {COMPARATIVO.map((r) => (
                <tr key={r.recurso} className="border-b border-[var(--cor-borda)] last:border-0">
                  <td className="py-2.5 text-[var(--cor-texto)]">{r.recurso} {r.chave && <span className="ml-1 font-mono text-[10px] text-[var(--cor-texto-suave)]">({r.chave})</span>}</td>
                  <td className="py-2.5 text-center">{r.free === "✓" ? <Check className="mx-auto h-4 w-4 text-[var(--cor-sucesso)]" /> : r.free === "—" ? <X className="mx-auto h-4 w-4 text-[var(--cor-texto-suave)]" /> : <span className="font-medium text-[var(--cor-texto)]">{r.free}</span>}</td>
                  <td className="py-2.5 text-center">{r.premium === "✓" ? <Check className="mx-auto h-4 w-4 text-[var(--cor-premium)]" /> : <span className="font-semibold text-[var(--cor-premium)]">{r.premium}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <AdsSlot id="planos-horizontal" formato="horizontal" className="my-6" />

      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><HelpCircle className="h-4 w-4 text-[var(--cor-primaria)]" /> Perguntas rápidas</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {FAQ.map((f) => <div key={f.q} className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><p className="text-sm font-medium text-[var(--cor-texto)]">{f.q}</p><p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{f.a}</p></div>)}
          <Separator className="bg-[var(--cor-borda)]" />
          <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]"><Sparkles className="h-4 w-4 text-[var(--cor-premium)]" /> Junte-se a <strong className="text-[var(--cor-texto)]">+12.000 assinantes</strong> que já leem sem anúncios.</div>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          {!ok ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><Crown className="h-5 w-5 text-[var(--cor-premium)]" /> Confirmar assinatura</DialogTitle>
                <DialogDescription>Revise seu plano antes de confirmar. Você pode cancelar quando quiser.</DialogDescription>
              </DialogHeader>
              {sel && (
                <div className="space-y-3">
                  <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4">
                    <p className="flex items-center justify-between text-sm font-semibold text-[var(--cor-texto)]">{sel.nome}<span className="text-[var(--cor-premium)]">R$ {sel.preco}</span></p>
                    <p className="text-xs text-[var(--cor-texto-suave)]">{sel.duracao_dias ? `${sel.duracao_dias} dias de acesso` : "Acesso gratuito"}</p>
                  </div>
                  <ul className="space-y-2 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-sm text-[var(--cor-texto)]">
                    {(sel.nome.toLowerCase().includes("premium") ? PREMIUM_BENEFICIOS.map((b) => b.text) : FREE_BENEFICIOS).map((b) => <li key={b} className="flex gap-2"><Check className="h-4 w-4 shrink-0 text-[var(--cor-premium)]" /> {b}</li>)}
                  </ul>
                  {!token && <p className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2 text-xs text-[var(--cor-texto-suave)]">Você precisa entrar na sua conta para assinar. Vamos te levar para o login.</p>}
                  {erro && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro}</p>}
                </div>
              )}
              <DialogFooter className="flex-col gap-2 sm:flex-col">
                <Button onClick={confirmar} disabled={loading || !sel} className="w-full min-h-[44px] bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-premium-hover)]">{loading ? "Confirmando…" : token ? "Confirmar assinatura" : "Entrar e assinar"}</Button>
                <Button variant="outline" onClick={() => setOpen(false)} className="w-full min-h-[44px] border-[var(--cor-borda)]">Voltar</Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader className="items-center text-center sm:items-center sm:text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-premium-suave)] text-[var(--cor-premium)]"><ShieldCheck className="h-6 w-6" /></div>
                <DialogTitle className="text-center">Assinatura confirmada!</DialogTitle>
                <DialogDescription className="text-center">Seu plano {sel?.nome} está ativo. Aproveite os benefícios Premium.</DialogDescription>
              </DialogHeader>
              <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-sm text-[var(--cor-texto-suave)] flex items-center gap-2"><Sparkles className="h-4 w-4 text-[var(--cor-premium)]" /> Sem anúncios e feed personalizado liberados.</div>
              <DialogFooter className="flex-col gap-2 sm:flex-col">
                <Button asChild className="w-full min-h-[44px] bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-premium-hover)]"><Link href="/minha-conta">Ver minha conta</Link></Button>
                <Button variant="outline" onClick={() => setOpen(false)} className="w-full min-h-[44px] border-[var(--cor-borda)]">Continuar navegando</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
