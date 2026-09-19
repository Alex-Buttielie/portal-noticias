"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatarRegiao, type Regiao } from "@/lib/regiao";
import { MapPin } from "lucide-react";

// ---------------------------------------------------------------------------
// Pergunta do SISTEMA (não do navegador): quando o GPS está bloqueado ou
// indisponível, detectamos a região aproximada pela conexão (IP) e
// perguntamos ao usuário se ele aceita usar. Assim o fluxo SEMPRE continua:
// o sistema pergunta, com ou sem prompt nativo do navegador.
// ---------------------------------------------------------------------------

export function PerguntaUsarLocal({
  regiao,
  aberto,
  onUsar,
  onDigitarCep,
}: {
  regiao: Regiao | null;
  aberto: boolean;
  onUsar: () => void;
  onDigitarCep: () => void;
}) {
  return (
    <Dialog open={aberto}>
      <DialogContent
        className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"
        aria-label="Confirmar localização detectada"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5 text-[var(--cor-primaria)]" aria-hidden />
            Usar esta localização?
          </DialogTitle>
          <DialogDescription>
            Detectamos{" "}
            <strong className="text-[var(--cor-texto)]">
              {regiao ? formatarRegiao(regiao) : "sua região"}
            </strong>{" "}
            pela sua conexão. Quer ver notícias daí? Usamos só cidade e estado — nada é rastreado.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            onClick={onUsar}
            className="min-h-[48px] flex-1 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"
          >
            Sim, usar {regiao ? formatarRegiao(regiao) : "minha região"}
          </Button>
          <Button type="button" variant="outline" onClick={onDigitarCep} className="min-h-[48px] flex-1">
            Digitar CEP
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
