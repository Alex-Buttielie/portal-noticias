"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Target } from "lucide-react";
import { atualizarObjetivoAssinatura, obterObjetivoAssinatura, ApiError } from "@/lib/api";

/**
 * Objetivo da assinatura Premium — texto livre do próprio usuário (por que
 * assinou). Guardado na conta (`PUT /api/assinatura/objetivo/`) e usado
 * por `lib/personalizar.ts#mapearObjetivoParaCategorias` para enviesar o
 * ranqueamento do feed: o algoritmo pondera mais as categorias que casam
 * com o que foi escrito aqui, sem nenhuma IA interpretando o texto.
 */
export function ObjetivoAssinatura({ token }: { token: string }) {
  const [valor, setValor] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    let ativo = true;
    obterObjetivoAssinatura(token)
      .then((r) => {
        if (ativo) setValor(r.objetivo || "");
      })
      .catch(() => {})
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, [token]);

  async function salvar() {
    setSalvando(true);
    try {
      await atualizarObjetivoAssinatura(valor, token);
      toast.success("Objetivo salvo — o feed vai levar isso em conta.");
    } catch (e: unknown) {
      toast.error(e instanceof ApiError ? e.message : "Não foi possível salvar agora.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
      <CardContent className="space-y-2 p-4">
        <h3 className="flex items-center gap-2 text-sm font-bold text-[var(--cor-texto)]">
          <Target className="h-4 w-4 text-[var(--cor-premium)]" aria-hidden /> Por que você assina o Premium?
        </h3>
        <p className="text-sm text-[var(--cor-texto-suave)]">
          Conte em poucas palavras o que você está buscando — usamos isso para ajustar o que aparece primeiro no seu feed.
        </p>
        <Textarea
          value={valor}
          onChange={(e) => setValor(e.target.value)}
          placeholder="Ex.: acompanhar economia para decidir sobre um investimento…"
          maxLength={500}
          disabled={carregando}
          className="min-h-[88px] border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-[var(--cor-texto-suave)]">{valor.length}/500</span>
          <Button size="sm" onClick={salvar} disabled={carregando || salvando} className="min-h-[36px]">
            {salvando ? "Salvando…" : "Salvar"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
