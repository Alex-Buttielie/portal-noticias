"use client";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FONTES_CATALOGO, obterMinhasFontes, alternarFonte } from "@/lib/minhas-fontes";
import { Newspaper, Plus, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export function MinhasFontes({ compact = false }: { compact?: boolean }) {
  const [seguidas, setSeguidas] = useState<string[]>([]);
  const [nova, setNova] = useState("");

  useEffect(() => {
    setSeguidas(obterMinhasFontes());
  }, []);

  const toggle = (nome: string) => setSeguidas(alternarFonte(nome));
  const segue = (nome: string) => seguidas.some((f) => f.toLowerCase() === nome.toLowerCase());

  const adicionar = () => {
    const nome = nova.trim();
    if (!nome) return;
    if (!segue(nome)) setSeguidas(alternarFonte(nome));
    setNova("");
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-[var(--cor-texto)]"><Newspaper className="h-4 w-4 text-[var(--cor-primaria)]" /> Minhas fontes</p>
        <Badge variant="outline" className="border-[var(--cor-borda)]">{seguidas.length} seguindo</Badge>
      </div>
      <div className="flex flex-wrap gap-2">
        {FONTES_CATALOGO.map((f) => {
          const on = segue(f);
          return (
            <button
              key={f}
              type="button"
              onClick={() => toggle(f)}
              aria-pressed={on}
              className={cn(
                "inline-flex min-h-[36px] items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                on
                  ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                  : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
              )}
            >
              {on && <Check className="h-3.5 w-3.5" />}
              {f}
            </button>
          );
        })}
      </div>
      {!compact && seguidas.filter((s) => !(FONTES_CATALOGO as readonly string[]).includes(s)).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {seguidas.filter((s) => !(FONTES_CATALOGO as readonly string[]).includes(s)).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => toggle(s)}
              aria-pressed
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded-full border border-[var(--cor-primaria)] bg-[var(--cor-primaria)] px-3 py-1.5 text-sm font-medium text-[var(--cor-texto-invertido)]"
            >
              <Check className="h-3.5 w-3.5" /> {s} <span aria-hidden>×</span>
            </button>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <div className="flex-1 space-y-1">
          <Label htmlFor="nova-fonte" className="sr-only">Adicionar fonte</Label>
          <Input
            id="nova-fonte"
            value={nova}
            onChange={(e) => setNova(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); adicionar(); } }}
            placeholder="Outra fonte (ex: Nexo, Poder360)…"
            className="h-10 bg-[var(--cor-fundo-card)]"
          />
        </div>
        <Button onClick={adicionar} disabled={!nova.trim()} variant="outline" className="min-h-[40px] shrink-0 gap-1 border-[var(--cor-borda)]"><Plus className="h-4 w-4" /> Seguir</Button>
      </div>
      <p className="text-xs text-[var(--cor-texto-suave)]">Você verá primeiro as notícias destas fontes. Vale na hora, sem salvar em servidor.</p>
    </div>
  );
}
