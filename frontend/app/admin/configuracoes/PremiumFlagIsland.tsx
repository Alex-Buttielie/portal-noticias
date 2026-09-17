"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth-context";
import {
  obterConfigSistemaAdmin,
  atualizarConfigSistemaAdmin,
} from "@/lib/api";
import { invalidarCachePremium } from "@/lib/premium";
import { Crown, Loader2 } from "lucide-react";

export function PremiumFlagIsland() {
  const { token } = useAuth();
  const tk = token || "";
  const [atual, setAtual] = useState<boolean | null>(null);
  const [pendente, setPendente] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [confirmaAbrir, setConfirmaAbrir] = useState(false);

  useEffect(() => {
    if (!tk) return;
    let vivo = true;
    setCarregando(true);
    setErro(null);
    obterConfigSistemaAdmin(tk)
      .then((cfg) => {
        if (!vivo) return;
        const v = cfg.premium_ativo === true;
        setAtual(v);
        setPendente(v);
      })
      .catch((e: unknown) => {
        if (!vivo) return;
        setErro(e instanceof Error ? e.message : "Não foi possível carregar a configuração.");
      })
      .finally(() => {
        if (vivo) setCarregando(false);
      });
    return () => {
      vivo = false;
    };
  }, [tk]);

  async function salvar(valor: boolean) {
    if (!tk) {
      setErro("Sessão expirada. Entre de novo como admin.");
      return;
    }
    setSalvando(true);
    setErro(null);
    setOk(null);
    try {
      const cfg = await atualizarConfigSistemaAdmin(tk, { premium_ativo: valor });
      const v = cfg.premium_ativo === true;
      setAtual(v);
      setPendente(v);
      invalidarCachePremium();
      setConfirmaAbrir(false);
      setOk(
        v
          ? "Premium ativado. Plano Free limitado, Premium pago."
          : "Premium desligado. Tudo liberado, assinaturas pausadas."
      );
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  function aoSalvar() {
    setOk(null);
    setErro(null);
    // Só pede confirmação ao LIGAR (vai restringir o acesso).
    if (pendente === true && atual === false) {
      setConfirmaAbrir(true);
      return;
    }
    void salvar(pendente);
  }

  if (!tk) {
    return (
      <p className="text-sm text-[var(--cor-texto-suave)]">
        Entre como admin para gerenciar os planos Premium.
      </p>
    );
  }

  const sujo = atual !== null && pendente !== atual;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-[var(--cor-texto)]">
          <Crown className="h-4 w-4 text-[var(--cor-premium)]" />
          Ativar planos Premium e limitar funcionalidades
        </p>
        {carregando ? (
          <Badge variant="outline" className="border-[var(--cor-borda)]">
            <Loader2 className="mr-1 h-3 w-3 animate-spin" /> carregando
          </Badge>
        ) : atual === true ? (
          <Badge className="bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]">
            ligado
          </Badge>
        ) : atual === false ? (
          <Badge
            variant="outline"
            className="border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]"
          >
            desligado — tudo liberado
          </Badge>
        ) : (
          <Badge variant="outline" className="border-[var(--cor-borda)]">
            —
          </Badge>
        )}
      </div>

      <p className="text-xs leading-relaxed text-[var(--cor-texto-suave)]">
        Desligado = tudo liberado para todos, assinaturas pausadas. Ligado = Free
        limitado, Premium pago.
      </p>

      <div className="flex flex-wrap items-center gap-3 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3">
        <label className="flex items-center gap-2 text-sm font-medium text-[var(--cor-texto)]">
          <Switch
            checked={pendente}
            onCheckedChange={setPendente}
            disabled={carregando || salvando || atual === null}
            aria-label="Ativar planos Premium"
          />
          {pendente ? "Ligado" : "Desligado"}
        </label>
        <span className="text-xs text-[var(--cor-texto-suave)]">
          Estado atual:{" "}
          {atual === null ? "…" : atual ? "ligado" : "desligado"}
        </span>
        <Button
          size="sm"
          onClick={aoSalvar}
          disabled={!sujo || salvando || carregando}
          className="ml-auto min-h-[36px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
        >
          {salvando && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
          Salvar
        </Button>
      </div>

      {erro && (
        <p
          role="alert"
          className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"
        >
          {erro}
        </p>
      )}
      {ok && (
        <p
          role="status"
          className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]"
        >
          {ok}
        </p>
      )}

      <Dialog open={confirmaAbrir} onOpenChange={setConfirmaAbrir}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Crown className="h-5 w-5 text-[var(--cor-premium)]" />
              Ligar o Premium?
            </DialogTitle>
            <DialogDescription>
              Isso vai restringir o acesso: o plano Free passa a ter limite e os
              recursos completos ficam só para assinantes. Dá para desligar de
              novo quando quiser.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setConfirmaAbrir(false)}
              disabled={salvando}
              className="border-[var(--cor-borda)]"
            >
              Voltar
            </Button>
            <Button
              onClick={() => void salvar(true)}
              disabled={salvando}
              className="bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]"
            >
              {salvando && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
              Ligar mesmo assim
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
