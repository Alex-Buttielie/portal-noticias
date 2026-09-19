"use client";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { MapPin, Locate, X } from "lucide-react";
import BuscaCep from "@/components/BuscaCep";
import { buscarCep, normalizaCep } from "@/lib/cep";
import {
  carregarRegiao, salvarRegiao, limparRegiao,
  obterRegiaoPorGeolocation, formatarRegiao, type Regiao,
} from "@/lib/regiao";

type Props = {
  value: Regiao | null;
  onChange: (r: Regiao | null) => void;
};

/** FRENTE 5 — local simples do Radar: 1 campo + geolocalização + CEP.
 *  Consentimento e persistência iguais aos da Home (SecaoRegiao):
 *  só cidade/estado, apaga quando quiser. */
export default function RadarLocalSimples({ value, onChange }: Props) {
  const [texto, setTexto] = useState("");
  const [buscando, setBuscando] = useState(false);
  const [resolvendo, setResolvendo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [cepOpen, setCepOpen] = useState(false);

  useEffect(() => {
    const salva = carregarRegiao();
    if (salva && !value) {
      onChange(salva);
      setTexto(salva.cidade && salva.estado ? `${salva.cidade}, ${salva.estado}` : salva.cidade || salva.estado || "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function detectar() {
    setBuscando(true); setErro(null);
    try {
      const r = await obterRegiaoPorGeolocation();
      salvarRegiao(r); onChange(r);
      setTexto(r.cidade && r.estado ? `${r.cidade}, ${r.estado}` : r.cidade || r.estado || "");
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Não foi possível obter sua localização.");
      setCepOpen(true);
    } finally {
      setBuscando(false);
    }
  }

  async function aplicarTexto() {
    const t = texto.trim();
    setErro(null);
    if (!t) { limparRegiao(); onChange(null); return; }
    const n = normalizaCep(t);
    if (n.length === 8) {
      setResolvendo(true);
      try {
        const e = await buscarCep(n);
        const r: Regiao = { cidade: e.localidade, estado: e.uf, pais: "Brasil", cep: e.cep, bairro: e.bairro, logradouro: e.logradouro };
        salvarRegiao(r); onChange(r);
        setTexto(r.cidade && r.estado ? `${r.cidade}, ${r.estado}` : t);
      } catch (e: unknown) {
        setErro(e instanceof Error ? e.message : "Não foi possível resolver este local.");
      } finally {
        setResolvendo(false);
      }
      return;
    }
    // "Cidade, UF" ou "Cidade" — mesmo formato que a Home/onboarding usam.
    const [cidade, resto] = t.split(",").map((s) => s.trim());
    if (!cidade) { setErro("Digite uma cidade, UF ou CEP."); return; }
    const estado = (resto || "").toUpperCase().slice(0, 2);
    const r: Regiao = { cidade, estado, pais: "Brasil" };
    salvarRegiao(r); onChange(r);
  }

  function aplicarCep(e: { cep: string; logradouro: string; bairro: string; localidade: string; uf: string }) {
    const r: Regiao = { cidade: e.localidade, estado: e.uf, pais: "Brasil", cep: e.cep, bairro: e.bairro, logradouro: e.logradouro };
    salvarRegiao(r); onChange(r);
    setTexto(r.cidade && r.estado ? `${r.cidade}, ${r.estado}` : "");
    setCepOpen(false); setErro(null);
  }

  function limpar() {
    limparRegiao(); onChange(null); setTexto(""); setErro(null);
  }

  return (
    <div className="space-y-2">
      <div className="space-y-1.5">
        <Label htmlFor="radar-local">Local</Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <MapPin className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-texto-suave)]" />
            <Input
              id="radar-local"
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); aplicarTexto(); } }}
              placeholder="São Paulo, SP ou 01310-100"
              autoComplete="address-level2"
              className="min-h-[44px] bg-[var(--cor-fundo-card)] pl-8"
              aria-describedby="radar-local-hint"
            />
          </div>
          <div className="flex gap-2">
            <Button type="button" onClick={aplicarTexto} disabled={resolvendo} className="min-h-[44px] flex-1 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] sm:flex-none">
              {resolvendo ? "Buscando…" : "Aplicar"}
            </Button>
            <Button type="button" variant="outline" onClick={detectar} disabled={buscando} className="min-h-[44px] flex-1 border-[var(--cor-borda)] sm:flex-none">
              <Locate className="mr-1.5 h-4 w-4" />{buscando ? "Localizando…" : "Detectar"}
            </Button>
          </div>
        </div>
        <p id="radar-local-hint" className="text-xs text-[var(--cor-texto-suave)]">
          Para ver tendências e evolução da sua cidade: detecte (o navegador pede permissão antes) ou digite cidade/UF ou CEP.
          Nada é detectado sozinho — só cidade/estado, sem rastreio. Apague quando quiser.
        </p>
      </div>

      <div aria-live="polite" aria-atomic="true">
        {erro && (
          <div role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">
            <p>{erro}</p>
            <button
              type="button"
              onClick={detectar}
              disabled={buscando}
              className="mt-1.5 inline-flex min-h-[36px] items-center gap-1 font-medium underline underline-offset-4 hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
            >
              {buscando ? "Tentando…" : "Tentar novamente"}
            </button>
          </div>
        )}
      </div>

      {value && (
        <p className="flex flex-wrap items-center gap-2 text-sm text-[var(--cor-texto)]">
          <Badge variant="outline" className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">{formatarRegiao(value)}</Badge>
          <button type="button" onClick={limpar} className="inline-flex min-h-[36px] items-center gap-1 text-xs text-[var(--cor-texto-suave)] underline underline-offset-4 hover:text-[var(--cor-texto)]">
            <X className="h-3 w-3" />Limpar
          </button>
        </p>
      )}

      <Collapsible open={cepOpen} onOpenChange={setCepOpen}>
        <CollapsibleTrigger asChild>
          <button type="button" className="text-xs text-[var(--cor-texto-suave)] underline underline-offset-4 hover:text-[var(--cor-texto)]">
            Prefiro buscar por CEP
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-2"><BuscaCep compact onEndereco={aplicarCep} /></CollapsibleContent>
      </Collapsible>
    </div>
  );
}
