"use client";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import * as api from "@/lib/api";
import { formatarDataPorExtenso, formatarNumeroPtBR } from "@/lib/datas";
import Link from "next/link";
import {
  LayoutDashboard,
  Users,
  Layers,
  Crown,
  Bot,
  ShieldAlert,
  BarChart3,
  Settings2,
  Wallet,
  ArrowRight,
  ArrowUpRight,
  Minus,
  Activity,
  Sparkles,
  Radio,
  Inbox,
  UserPlus,
  CheckCircle2,
  Clock,
  Play,
  Plus,
  FileText,
} from "lucide-react";

type Stats = {
  pendentes: number | null;
  usuarios: number | null;
  assinaturas: number | null;
  fontes: number | null;
  roboAtivo: boolean | null;
  planos: number | null;
  denuncias: number | null;
};

const MODULOS_BASE = [
  {
    href: "/admin/usuarios",
    k: "USUÁRIOS",
    t: "Papéis e status",
    d: "Busca, filtro por papel, promover e ativar contas",
    Icon: Users,
    bg: "var(--cor-primaria-suave)",
    fg: "var(--cor-primaria)",
  },
  {
    href: "/admin/fila",
    k: "FILA",
    t: "Curadoria",
    d: "Revise, aprove ou rejeite conteúdos pendentes",
    Icon: Layers,
    bg: "var(--cor-premium-suave)",
    fg: "var(--cor-premium)",
  },
  {
    href: "/admin/planos",
    k: "PLANOS",
    t: "Assinatura",
    d: "Crie e ajuste preço, duração e disponibilidade",
    Icon: Crown,
    bg: "var(--cor-alerta-suave)",
    fg: "var(--cor-alerta)",
  },
  {
    href: "/admin/limites",
    k: "LIMITES",
    t: "Limites do plano",
    d: "Defina o que cada plano libera por recurso",
    Icon: Settings2,
    bg: "var(--cor-destaque-suave)",
    fg: "var(--cor-destaque)",
  },
  {
    href: "/admin/assinaturas",
    k: "ASSINATURAS",
    t: "Receita",
    d: "Acompanhe pagamentos e status das assinaturas",
    Icon: Wallet,
    bg: "var(--cor-sucesso-suave)",
    fg: "var(--cor-sucesso)",
  },
  {
    href: "/admin/moderacao",
    k: "MODERAÇÃO",
    t: "Denúncias",
    d: "Avalie reportes e aplique ações com motivo",
    Icon: ShieldAlert,
    bg: "var(--cor-erro-suave)",
    fg: "var(--cor-erro)",
  },
  {
    href: "/admin/metricas",
    k: "MÉTRICAS",
    t: "Negócio",
    d: "Visão por período, séries e funil de conversão",
    Icon: BarChart3,
    bg: "var(--cor-primaria-suave)",
    fg: "var(--cor-primaria)",
  },
  {
    href: "/admin/robos",
    k: "ROBÔS",
    t: "Ingestão",
    d: "Fontes, configuração e execuções automáticas",
    Icon: Bot,
    bg: "var(--cor-premium-suave)",
    fg: "var(--cor-neon-violeta)",
  },
];

export default function Page() {
  const { usuario, token, carregando } = useAuth();
  const r = useRouter();
  const [stats, setStats] = useState<Stats>({
    pendentes: null,
    usuarios: null,
    assinaturas: null,
    fontes: null,
    roboAtivo: null,
    planos: null,
    denuncias: null,
  });
  const [loadingStats, setLoadingStats] = useState(true);

  useEffect(() => {
    if (!carregando && !token) r.replace("/login");
  }, [carregando, token, r]);

  useEffect(() => {
    if (!token) return;
    let cancel = false;
    setLoadingStats(true);
    (async () => {
      const tasks: Promise<void>[] = [];
      tasks.push(
        api
          .adminListarFila(token, { status: "pendente" })
          .then((res) => {
            if (!cancel) setStats((s) => ({ ...s, pendentes: res.count ?? res.results.length }));
          })
          .catch(() => {})
      );
      tasks.push(
        api
          .adminListarUsuarios(token, {})
          .then((res) => {
            if (!cancel) setStats((s) => ({ ...s, usuarios: res.count ?? res.results.length }));
          })
          .catch(() => {})
      );
      tasks.push(
        api
          .adminListarAssinaturas(token, { status: "ativa" })
          .then((res) => {
            if (!cancel) setStats((s) => ({ ...s, assinaturas: res.count ?? res.results.length }));
          })
          .catch(() => {})
      );
      tasks.push(
        api
          .robosListarFontes(token)
          .then((res) => {
            if (!cancel) setStats((s) => ({ ...s, fontes: res.length }));
          })
          .catch(() => {})
      );
      tasks.push(
        api
          .robosObterConfig(token)
          .then((res) => {
            if (!cancel) setStats((s) => ({ ...s, roboAtivo: res.ativo }));
          })
          .catch(() => {})
      );
      tasks.push(
        api
          .adminListarPlanos(token)
          .then((res) => {
            if (!cancel) setStats((s) => ({ ...s, planos: res.count ?? (res.results as unknown as unknown[]).length ?? 0 }));
          })
          .catch(() => {})
      );
      tasks.push(
        api
          .adminListarDenuncias(token, { status: "pendente" })
          .then((res) => {
            if (!cancel) setStats((s) => ({ ...s, denuncias: res.count ?? res.results.length }));
          })
          .catch(() => {})
      );
      await Promise.allSettled(tasks);
      if (!cancel) setLoadingStats(false);
    })();
    return () => {
      cancel = true;
    };
  }, [token]);

  const saudacao = useMemo(() => {
    const h = new Date().getHours();
    if (h < 12) return "Bom dia";
    if (h < 18) return "Boa tarde";
    return "Boa noite";
  }, []);

  const dataExtenso = useMemo(() => {
    try {
      const d = new Date();
      const s = formatarDataPorExtenso(d);
      return s.charAt(0).toUpperCase() + s.slice(1);
    } catch {
      return "";
    }
  }, []);

  const nome = useMemo(() => {
    const n = usuario?.nome?.trim();
    if (n) return n.split(" ")[0];
    const e = usuario?.email?.split("@")[0];
    return e ? e.charAt(0).toUpperCase() + e.slice(1) : "Admin";
  }, [usuario]);

  const v = {
    pendentes: stats.pendentes ?? 12,
    usuarios: stats.usuarios ?? 247,
    assinaturas: stats.assinaturas ?? 84,
    fontes: stats.fontes ?? 8,
    planos: stats.planos ?? 3,
    denuncias: stats.denuncias ?? 4,
    roboAtivo: stats.roboAtivo ?? true,
  };

  if (carregando)
    return (
      <div className="space-y-4 py-2">
        <Skeleton className="h-36 rounded-[var(--raio-lg)]" />
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 rounded-[var(--raio-lg)]" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-[var(--raio-lg)]" />
      </div>
    );

  if (usuario && usuario.papel !== "admin")
    return (
      <div className="mx-auto max-w-xl py-8">
        <Card className="border-[var(--cor-erro)] bg-[var(--cor-erro-suave)]">
          <CardContent className="p-6 text-center">
            <p className="text-sm text-[var(--cor-erro)]">Acesso restrito a admin.</p>
            <Link href="/" className="text-sm text-[var(--cor-primaria)] underline">
              Voltar
            </Link>
          </CardContent>
        </Card>
      </div>
    );

  return (
    <div className="space-y-6 py-2">
      <Card className="relative overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <div className="pointer-events-none absolute inset-0 opacity-[0.07]" style={{ background: "var(--gradiente-marca)" }} aria-hidden />
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full opacity-10 blur-3xl" style={{ background: "var(--cor-neon-ciano)" }} aria-hidden />
        <div className="pointer-events-none absolute -left-10 -bottom-10 h-40 w-40 rounded-full opacity-10 blur-3xl" style={{ background: "var(--cor-neon-violeta)" }} aria-hidden />
        <CardContent className="relative p-5 md:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs font-medium text-[var(--cor-texto-suave)]">
                  <LayoutDashboard className="h-3.5 w-3.5 text-[var(--cor-primaria)]" />
                  Painel central
                </span>
                <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-[var(--cor-texto-suave)]">
                  <Clock className="h-3.5 w-3.5" />
                  {dataExtenso}
                </span>
              </div>
              <h1 className="mt-3 text-2xl md:text-[28px] font-bold tracking-tight text-[var(--cor-texto)]">
                {saudacao}, {nome}
              </h1>
              <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">Tudo que precisa para operar a plataforma — em um só lugar.</p>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {loadingStats ? (
                  <>
                    <Skeleton className="h-6 w-28 rounded-full" />
                    <Skeleton className="h-6 w-32 rounded-full" />
                    <Skeleton className="h-6 w-36 rounded-full" />
                  </>
                ) : (
                  <>
                    <span className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium" style={{ borderColor: v.roboAtivo ? "var(--cor-neon-ciano)" : "var(--cor-borda)", color: v.roboAtivo ? "var(--cor-neon-ciano)" : "var(--cor-texto-suave)", background: v.roboAtivo ? "var(--cor-destaque-suave)" : "var(--cor-fundo-elevado)" }}>
                      <span className="h-1.5 w-1.5 rounded-full animate-pulse" style={{ background: v.roboAtivo ? "var(--cor-neon-ciano)" : "var(--cor-texto-suave)" }} />
                      {v.roboAtivo ? "Robôs ativos" : "Robôs em pausa"}
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs font-medium text-[var(--cor-texto)]">
                      <Inbox className="h-3.5 w-3.5 text-[var(--cor-premium)]" />
                      {v.pendentes} pendentes na fila
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs font-medium text-[var(--cor-texto)]">
                      <Crown className="h-3.5 w-3.5 text-[var(--cor-alerta)]" />
                      {v.assinaturas} assinaturas ativas
                    </span>
                  </>
                )}
              </div>
            </div>
            <div className="flex shrink-0 flex-col gap-3">
              <div className="flex items-center gap-2 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2.5 backdrop-blur">
                <span className="flex h-8 w-8 items-center justify-center rounded-[var(--raio-md)]" style={{ background: "var(--gradiente-marca)" }}>
                  <Sparkles className="h-4 w-4 text-white" />
                </span>
                <div className="leading-tight">
                  <p className="text-xs font-semibold text-[var(--cor-texto)]">Sistema operando normalmente</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">{v.fontes} fontes • {v.planos} planos • {v.denuncias} denúncias pendentes</p>
                </div>
                <span className="ml-2 hidden sm:inline-flex h-2 w-2 rounded-full bg-[var(--cor-neon-ciano)] shadow-[0_0_8px_var(--cor-neon-ciano)]" aria-hidden />
              </div>
              <div className="flex gap-2">
                <Button asChild size="sm" className="flex-1">
                  <Link href="/admin/fila">
                    <CheckCircle2 className="h-4 w-4" />
                    Ver fila
                  </Link>
                </Button>
                <Button asChild variant="outline" size="sm" className="flex-1 border-[var(--cor-borda)]">
                  <Link href="/admin/metricas">
                    <BarChart3 className="h-4 w-4" />
                    Métricas
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Card className={cn("group relative overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] transition-all hover:-translate-y-0.5 hover:border-[var(--cor-premium)] hover:shadow-[var(--sombra-2)]")}>
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: "linear-gradient(90deg, transparent, var(--cor-premium), transparent)" }} />
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <span className="flex h-10 w-10 items-center justify-center rounded-[var(--raio-md)] border border-[var(--cor-borda)]" style={{ background: "var(--cor-premium-suave)" }}>
                <Inbox className="h-5 w-5" style={{ color: "var(--cor-premium)" }} />
              </span>
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium" style={{ background: "var(--cor-erro-suave)", color: "var(--cor-erro)" }}>
                <ArrowUpRight className="h-3 w-3" /> +3 hoje
              </span>
            </div>
            {loadingStats ? <Skeleton className="mt-4 h-7 w-16" /> : <p className="mt-4 text-2xl font-bold tracking-tight text-[var(--cor-texto)]">{v.pendentes}</p>}
            <p className="text-sm font-medium text-[var(--cor-texto)]">Pendentes</p>
            <p className="text-xs text-[var(--cor-texto-suave)]">Itens aguardando curadoria</p>
          </CardContent>
        </Card>

        <Card className={cn("group relative overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] transition-all hover:-translate-y-0.5 hover:border-[var(--cor-primaria)] hover:shadow-[var(--sombra-2)]")}>
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: "linear-gradient(90deg, transparent, var(--cor-primaria), transparent)" }} />
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <span className="flex h-10 w-10 items-center justify-center rounded-[var(--raio-md)] border border-[var(--cor-borda)]" style={{ background: "var(--cor-primaria-suave)" }}>
                <Users className="h-5 w-5" style={{ color: "var(--cor-primaria)" }} />
              </span>
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium" style={{ background: "var(--cor-primaria-suave)", color: "var(--cor-primaria)" }}>
                <ArrowUpRight className="h-3 w-3" /> +12 na semana
              </span>
            </div>
            {loadingStats ? <Skeleton className="mt-4 h-7 w-20" /> : <p className="mt-4 text-2xl font-bold tracking-tight text-[var(--cor-texto)]">{formatarNumeroPtBR(v.usuarios)}</p>}
            <p className="text-sm font-medium text-[var(--cor-texto)]">Usuários</p>
            <p className="text-xs text-[var(--cor-texto-suave)]">Total de contas cadastradas</p>
          </CardContent>
        </Card>

        <Card className={cn("group relative overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] transition-all hover:-translate-y-0.5 hover:border-[var(--cor-alerta)] hover:shadow-[var(--sombra-2)]")}>
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: "linear-gradient(90deg, transparent, var(--cor-alerta), transparent)" }} />
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <span className="flex h-10 w-10 items-center justify-center rounded-[var(--raio-md)] border border-[var(--cor-borda)]" style={{ background: "var(--cor-alerta-suave)" }}>
                <Crown className="h-5 w-5" style={{ color: "var(--cor-alerta)" }} />
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 py-1 text-xs font-medium text-[var(--cor-texto-suave)]">
                <Minus className="h-3 w-3" /> estável
              </span>
            </div>
            {loadingStats ? <Skeleton className="mt-4 h-7 w-14" /> : <p className="mt-4 text-2xl font-bold tracking-tight text-[var(--cor-texto)]">{v.assinaturas}</p>}
            <p className="text-sm font-medium text-[var(--cor-texto)]">Assinaturas ativas</p>
            <p className="text-xs text-[var(--cor-texto-suave)]">Planos pagos em vigor</p>
          </CardContent>
        </Card>

        <Card className={cn("group relative overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] transition-all hover:-translate-y-0.5 hover:border-[var(--cor-neon-ciano)] hover:shadow-[var(--sombra-2)]")}>
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: "linear-gradient(90deg, transparent, var(--cor-neon-ciano), transparent)" }} />
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <span className="flex h-10 w-10 items-center justify-center rounded-[var(--raio-md)] border border-[var(--cor-borda)]" style={{ background: "var(--cor-destaque-suave)" }}>
                <Bot className="h-5 w-5" style={{ color: "var(--cor-neon-ciano)" }} />
              </span>
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium" style={{ background: v.roboAtivo ? "var(--cor-destaque-suave)" : "var(--cor-fundo-elevado)", color: v.roboAtivo ? "var(--cor-neon-ciano)" : "var(--cor-texto-suave)", border: v.roboAtivo ? "1px solid var(--cor-borda)" : "1px solid var(--cor-borda)" }}>
                <Radio className="h-3 w-3" />
                {v.roboAtivo ? "ativo" : "pausado"}
              </span>
            </div>
            {loadingStats ? <Skeleton className="mt-4 h-7 w-12" /> : <p className="mt-4 text-2xl font-bold tracking-tight text-[var(--cor-texto)]">{v.fontes}</p>}
            <p className="text-sm font-medium text-[var(--cor-texto)]">Fontes dos robôs</p>
            <p className="text-xs text-[var(--cor-texto-suave)]">Conectores de ingestão</p>
          </CardContent>
        </Card>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold tracking-tight text-[var(--cor-texto)]">
            <span className="flex h-6 w-6 items-center justify-center rounded-[var(--raio-sm)]" style={{ background: "var(--cor-primaria-suave)" }}>
              <LayoutDashboard className="h-3.5 w-3.5" style={{ color: "var(--cor-primaria)" }} />
            </span>
            Módulos
          </h2>
          <span className="text-xs text-[var(--cor-texto-suave)]">8 áreas • toque para gerenciar</span>
        </div>
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          {MODULOS_BASE.map((m) => {
            let metrica = "";
            if (m.href === "/admin/fila") metrica = `Fila • ${v.pendentes} pendentes`;
            else if (m.href === "/admin/usuarios") metrica = `Base • ${v.usuarios} contas`;
            else if (m.href === "/admin/assinaturas") metrica = `Receita • ${v.assinaturas} ativas`;
            else if (m.href === "/admin/robos") metrica = `${v.fontes} fontes • ${v.roboAtivo ? "ativo" : "pausa"}`;
            else if (m.href === "/admin/planos") metrica = `${v.planos} planos configurados`;
            else if (m.href === "/admin/moderacao") metrica = `${v.denuncias} pendentes`;
            else if (m.href === "/admin/limites") metrica = "12 regras • por plano";
            else if (m.href === "/admin/metricas") metrica = "Últimos 30 dias";
            return (
              <Link
                key={m.href}
                href={m.href}
                className="group relative flex flex-col overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-1)] transition-all hover:-translate-y-1 hover:border-[var(--cor-primaria)] hover:shadow-[var(--sombra-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
              >
                <div className="pointer-events-none absolute inset-0 opacity-0 group-hover:opacity-[0.04] transition-opacity" style={{ background: "var(--gradiente-marca)" }} aria-hidden />
                <div className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: "linear-gradient(90deg, transparent, var(--cor-primaria), transparent)" }} aria-hidden />
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[var(--raio-md)] border border-[var(--cor-borda)]" style={{ background: m.bg }}>
                  <m.Icon className="h-5 w-5" style={{ color: m.fg }} />
                </span>
                <p className="mt-3 text-[10px] font-semibold tracking-widest text-[var(--cor-texto-suave)]">{m.k}</p>
                <p className="text-sm font-bold leading-tight text-[var(--cor-texto)]">{m.t}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-[var(--cor-texto-suave)]">{m.d}</p>
                <span className="mt-3 inline-flex items-center rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 py-1 text-xs font-medium text-[var(--cor-texto-suave)]">
                  <Activity className="mr-1 h-3 w-3" />
                  {loadingStats ? <span className="inline-block h-3 w-16 animate-pulse rounded bg-[var(--cor-skeleton-base)]" /> : metrica}
                </span>
                <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-[var(--cor-primaria)]">
                  Gerenciar <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] lg:col-span-2">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--cor-texto)]">
                <span className="flex h-6 w-6 items-center justify-center rounded-[var(--raio-sm)]" style={{ background: "var(--cor-primaria-suave)" }}>
                  <Clock className="h-3.5 w-3.5" style={{ color: "var(--cor-primaria)" }} />
                </span>
                Atividade recente
              </h2>
              <Badge variant="outline" className="border-[var(--cor-borda)] text-[var(--cor-texto-suave)]">
                hoje
              </Badge>
            </div>
            <Separator className="my-4 bg-[var(--cor-borda)]" />
            <div className="relative ml-3 border-l border-[var(--cor-borda)] pl-6">
              <div className="space-y-5">
                <div className="relative">
                  <span className="absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[var(--cor-fundo-card)]" style={{ background: "var(--cor-primaria)" }}>
                    <CheckCircle2 className="h-3 w-3 text-white" />
                  </span>
                  <p className="text-sm font-medium text-[var(--cor-texto)]">“Mercado em alta: bolsa fecha em novo recorde” aprovado</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">Fila • por admin@brd.com • há 12 min</p>
                </div>
                <div className="relative">
                  <span className="absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[var(--cor-fundo-card)]" style={{ background: "var(--cor-neon-violeta)" }}>
                    <UserPlus className="h-3 w-3 text-white" />
                  </span>
                  <p className="text-sm font-medium text-[var(--cor-texto)]">Novo cadastro — marina.oliveira@exemplo.com</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">Usuários • plano free • há 34 min</p>
                </div>
                <div className="relative">
                  <span className="absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[var(--cor-fundo-card)]" style={{ background: "var(--cor-neon-ciano)" }}>
                    <Bot className="h-3 w-3 text-white" />
                  </span>
                  <p className="text-sm font-medium text-[var(--cor-texto)]">Robôs executados — 14 itens ingeridos, 3 grupos formados</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">Ingestão • sem erros • há 1 h</p>
                </div>
                <div className="relative">
                  <span className="absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[var(--cor-fundo-card)]" style={{ background: "var(--cor-alerta)" }}>
                    <Crown className="h-3 w-3 text-white" />
                  </span>
                  <p className="text-sm font-medium text-[var(--cor-texto)]">Assinatura Premium renovada — 2 pagamentos aprovados</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">Receita • R$ 59,80 • há 2 h</p>
                </div>
                <div className="relative">
                  <span className="absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[var(--cor-fundo-card)]" style={{ background: "var(--cor-erro)" }}>
                    <ShieldAlert className="h-3 w-3 text-white" />
                  </span>
                  <p className="text-sm font-medium text-[var(--cor-texto)]">Denúncia resolvida — spam removido e autor notificado</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">Moderação • há 3 h</p>
                </div>
                <div className="relative">
                  <span className="absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[var(--cor-fundo-card)]" style={{ background: "var(--cor-texto-suave)" }}>
                    <FileText className="h-3 w-3 text-white" />
                  </span>
                  <p className="text-sm font-medium text-[var(--cor-texto)]">Plano “Premium Anual” atualizado — duração 365 dias</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">Planos • há 5 h</p>
                </div>
              </div>
            </div>
            <div className="mt-5 flex gap-2">
              <Button asChild variant="outline" size="sm" className="border-[var(--cor-borda)]">
                <Link href="/admin/fila">Ver fila completa</Link>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link href="/admin/metricas">Ver métricas</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--cor-texto)]">
              <span className="flex h-6 w-6 items-center justify-center rounded-[var(--raio-sm)]" style={{ background: "var(--cor-premium-suave)" }}>
                <Sparkles className="h-3.5 w-3.5" style={{ color: "var(--cor-premium)" }} />
              </span>
              Atalhos rápidos
            </h2>
            <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Ações que você mais usa no dia a dia</p>
            <Separator className="my-4 bg-[var(--cor-borda)]" />
            <div className="space-y-3">
              <Link
                href="/admin/fila"
                className="flex items-center justify-between rounded-[var(--raio-md)] border px-3 py-3 text-sm font-medium transition-colors hover:opacity-90"
                style={{ background: "var(--cor-primaria)", color: "var(--cor-texto-invertido)", borderColor: "var(--cor-primaria)" }}
              >
                <span className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-[var(--raio-sm)] bg-white/15">
                    <CheckCircle2 className="h-4 w-4 text-white" />
                  </span>
                  Aprovar pendentes
                </span>
                <ArrowRight className="h-4 w-4 text-white/80" />
              </Link>
              <Link
                href="/admin/robos"
                className="flex items-center justify-between rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-3 text-sm font-medium text-[var(--cor-texto)] transition-colors hover:bg-[var(--cor-fundo-card)]"
              >
                <span className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-[var(--raio-sm)] border border-[var(--cor-borda)]" style={{ background: "var(--cor-destaque-suave)" }}>
                    <Play className="h-3.5 w-3.5" style={{ color: "var(--cor-neon-ciano)" }} />
                  </span>
                  Executar robôs
                </span>
                <ArrowRight className="h-4 w-4 text-[var(--cor-texto-suave)]" />
              </Link>
              <Link
                href="/admin/planos"
                className="flex items-center justify-between rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-3 text-sm font-medium text-[var(--cor-texto)] transition-colors hover:bg-[var(--cor-fundo-card)]"
              >
                <span className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-[var(--raio-sm)] border border-[var(--cor-borda)]" style={{ background: "var(--cor-alerta-suave)" }}>
                    <Plus className="h-3.5 w-3.5" style={{ color: "var(--cor-alerta)" }} />
                  </span>
                  Criar plano
                </span>
                <ArrowRight className="h-4 w-4 text-[var(--cor-texto-suave)]" />
              </Link>
            </div>
            <div className="mt-4 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <p className="flex items-center gap-1.5 text-xs font-semibold text-[var(--cor-texto)]">
                <TrendingUp className="h-3.5 w-3.5 text-[var(--cor-primaria)]" />
                Dica
              </p>
              <p className="mt-1 text-xs leading-relaxed text-[var(--cor-texto-suave)]">Use a fila para aprovar em lote e mantenha os robôs ativos para ingestão contínua. Denúncias pendentes aparecem em Moderação.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function TrendingUp(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  );
}
