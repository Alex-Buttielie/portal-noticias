"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import { useQueryAdminFontes } from "@/lib/queries";
import { Newspaper, ArrowRight } from "lucide-react";

/**
 * C-06 (implementation-contract.md run 20261013-1048-home-radar-central-ux,
 * Bloco C): o CRUD completo de fontes RSS vivia duplicado aqui E em
 * `/admin/robos` (aba Fontes — busca, filtro, edição inline, teste de URL,
 * remoção com confirmação). Mantemos a implementação completa em um lugar
 * só (`/admin/robos`, já mais completa) — este componente passa a ser só um
 * atalho/resumo, sem reimplementar nenhuma lógica de mutação.
 */
export function FontesIsland() {
  const { usuario, token } = useAuth();
  const consulta = useQueryAdminFontes({ token, usuarioId: usuario?.id ?? 0 });
  const fontes = consulta.isError ? [] : (consulta.data ?? []);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-[var(--cor-texto)]"><Newspaper className="h-4 w-4 text-[var(--cor-primaria)]" /> Fontes dos robôs</p>
        <Badge variant="outline" className="border-[var(--cor-borda)]">{fontes.filter((f) => f.ativo).length} ativas / {fontes.length} total</Badge>
      </div>
      <p className="text-xs leading-relaxed text-[var(--cor-texto-suave)]">
        Criar, editar, ativar/pausar e remover fontes RSS é feito em <strong>Robôs → Fontes</strong> — único lugar com o CRUD completo
        (busca, filtro por status e teste de URL), para não ter duas telas mantendo a mesma coisa.
      </p>
      <Button asChild size="sm" className="min-h-[40px] gap-1.5 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
        <Link href="/admin/robos?aba=fontes">
          Gerenciar fontes <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Button>
    </div>
  );
}
