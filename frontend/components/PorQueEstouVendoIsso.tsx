"use client";

import { useState } from "react";
import { Info } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function PorQueEstouVendoIsso({ motivos }: { motivos: string[] }) {
  const [aberto, setAberto] = useState(false);

  if (motivos.length === 0) return null;

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variante="outline"
          tamanho="pequeno"
          className={cn("rounded-full border-dashed gap-1.5")}
          aria-expanded={aberto}
        >
          <Info className="h-3.5 w-3.5" aria-hidden="true" /> Por que estou vendo isso?
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)]">
            Por que este conteúdo apareceu
          </DialogTitle>
          <DialogDescription className="sr-only">
            Critérios que fizeram este conteúdo aparecer para você
          </DialogDescription>
        </DialogHeader>
        <ul className="mt-3 flex min-w-0 flex-col gap-2 text-sm">
          {motivos.map((motivo) => (
            <li key={motivo} className="flex min-w-0 gap-2 leading-relaxed">
              <span className="shrink-0 text-[var(--cor-primaria)]" aria-hidden="true">
                •
              </span>
              <span className="min-w-0 break-words">{motivo}</span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
