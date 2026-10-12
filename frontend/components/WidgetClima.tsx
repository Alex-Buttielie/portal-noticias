"use client";
import { useEffect, useState } from "react";
import { Sun, Cloud, CloudRain, CloudLightning, Snowflake, CloudFog } from "lucide-react";
import { obterClima, interpretarCodigoClima, type Clima } from "@/lib/clima";
import type { Regiao } from "@/lib/regiao";

const ICONES = {
  sol: Sun,
  nublado: Cloud,
  chuva: CloudRain,
  tempestade: CloudLightning,
  neve: Snowflake,
  neblina: CloudFog,
};

const DIAS_SEMANA = ["dom.", "seg.", "ter.", "qua.", "qui.", "sex.", "sáb."];

function rotuloDia(iso: string, index: number): string {
  if (index === 0) return "Hoje";
  return DIAS_SEMANA[new Date(`${iso}T12:00:00`).getDay()];
}

/**
 * Clima da região do leitor — inspirado no widget do Google Notícias.
 * Só aparece quando há uma `Regiao` salva (mesmo consentimento usado por
 * `SecaoRegiao`) e a API responde; qualquer falha, o componente some.
 */
export function WidgetClima({ regiao }: { regiao: Regiao }) {
  const [clima, setClima] = useState<Clima | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    let ativo = true;
    obterClima(regiao).then((c) => {
      if (!ativo) return;
      if (c) setClima(c);
      else setFalhou(true);
    });
    return () => {
      ativo = false;
    };
  }, [regiao]);

  if (falhou || !clima) return null;

  const atual = interpretarCodigoClima(clima.codigoAtual);
  const IconeAtual = ICONES[atual.icone];

  return (
    <div className="flex shrink-0 items-center gap-3 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2" aria-label={`Clima em ${clima.cidade}: ${atual.rotulo}, ${clima.temperaturaAtual} graus`}>
      <IconeAtual className="h-6 w-6 shrink-0 text-[var(--cor-primaria)]" aria-hidden />
      <div className="min-w-0">
        <p className="text-sm font-bold leading-none text-[var(--cor-texto)]">{clima.temperaturaAtual}°</p>
        <p className="mt-0.5 truncate text-xs leading-none text-[var(--cor-texto-suave)]">{clima.cidade || atual.rotulo}</p>
      </div>
      <div className="hidden items-center gap-2 border-l border-[var(--cor-borda)] pl-3 sm:flex">
        {clima.previsao.slice(1, 4).map((dia, i) => {
          const info = interpretarCodigoClima(dia.codigo);
          const Icone = ICONES[info.icone];
          return (
            <div key={dia.data} className="flex flex-col items-center gap-0.5" title={info.rotulo}>
              <span className="text-[10px] font-medium text-[var(--cor-texto-suave)]">{rotuloDia(dia.data, i + 1)}</span>
              <Icone className="h-3.5 w-3.5 text-[var(--cor-texto-suave)]" aria-hidden />
              <span className="text-[10px] text-[var(--cor-texto-suave)]">{dia.max}°/{dia.min}°</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
