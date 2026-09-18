"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { MapPin, Search, Loader2, Check } from "lucide-react";
import { buscarCep, normalizaCep, type EnderecoViaCep } from "@/lib/cep";

function mascaraCep(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 8);
  if (d.length <= 5) return d;
  return `${d.slice(0, 5)}-${d.slice(5)}`;
}

type Props = {
  value: string;
  onChange: (v: string) => void;
  onEndereco?: (e: EnderecoViaCep) => void;
  placeholder?: string;
  label?: string;
  id?: string;
  compact?: boolean;
};

export default function EnderecoAutocomplete({ value, onChange, onEndereco, placeholder = "01310-100 ou Av. Paulista", label, id = "endereco-autocomplete", compact }: Props) {
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<EnderecoViaCep | null>(null);
  const [sugErro, setSugErro] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abort = useRef<AbortController | null>(null);

  const doBuscarCep = useCallback(async (raw: string) => {
    const n = normalizaCep(raw);
    if (n.length !== 8) { setErro("Digite 8 dígitos do CEP para preencher automático."); setResultado(null); return; }
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setLoading(true); setErro(null); setResultado(null); setSugErro(null);
    try {
      const e = await buscarCep(n, { signal: ctrl.signal });
      if (ctrl.signal.aborted) return;
      setResultado(e);
      onEndereco?.(e);
    } catch (e: unknown) {
      if (e instanceof DOMException && (e as DOMException).name === "AbortError") return;
      setErro(e instanceof Error ? e.message : "Falha ao buscar CEP.");
    }
    finally { if (abort.current === ctrl) setLoading(false); }
  }, [onEndereco]);

  const doBuscarManual = useCallback(async () => {
    setSugErro(null);
    const n = normalizaCep(value);
    if (n.length === 8) { await doBuscarCep(value); return; }
    const v = value.trim();
    if (v.length < 3) { setErro("Digite 8 dígitos do CEP ou ao menos 3 letras para buscar."); return; }
    setErro(null);
    setSugErro("Para buscar por logradouro use CEP ou informe UF, cidade e rua na busca avançada.");
  }, [value, doBuscarCep]);

  useEffect(() => {
    const n = normalizaCep(value);
    if (n.length !== 8) {
      if (timer.current) clearTimeout(timer.current);
      if (n.length === 0) { setErro(null); setResultado(null); setSugErro(null); }
      else if (value.trim().length >= 3) { setErro(null); }
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { doBuscarCep(value); }, 400);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [value, doBuscarCep]);

  const handleUsar = (e: EnderecoViaCep) => {
    setResultado(e);
    onChange(mascaraCep(e.cep) || e.cep);
    onEndereco?.(e);
  };

  const nCep = normalizaCep(value);
  const valido = !!resultado && !erro && nCep.length === 8;
  const invalido = !!erro;
  const isLogradouro = nCep.length !== 8 && value.trim().length >= 3;

  return (
    <div className={cn("space-y-1.5", compact && "space-y-1")}>
      {label && <Label htmlFor={id}>{label}</Label>}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <MapPin className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-texto-suave)]" />
          <Input
            id={id}
            value={value}
            onChange={(e) => {
              const v = e.target.value;
              const n = normalizaCep(v);
              if (/^[\d\s-]+$/.test(v) && n.length <= 8 && v.trim().length <= 9) onChange(mascaraCep(v));
              else onChange(v);
            }}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (timer.current) clearTimeout(timer.current); doBuscarManual(); } }}
            placeholder={placeholder}
            className={cn("bg-[var(--cor-fundo-card)] pl-8 transition-colors", invalido ? "border-[var(--cor-erro)] focus-visible:ring-[var(--cor-erro)]" : valido ? "border-[var(--cor-sucesso)] focus-visible:ring-[var(--cor-sucesso)]" : "")}
            aria-invalid={invalido}
            aria-label={label ?? "Endereço"}
          />
          {valido && !loading && <Check className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-sucesso)]" />}
          {loading && <Loader2 className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-[var(--cor-texto-suave)]" />}
        </div>
        <Button type="button" onClick={doBuscarManual} disabled={loading} className="min-h-[44px] min-w-[96px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          <span className="ml-1.5">{loading ? "Buscando…" : "Buscar"}</span>
        </Button>
      </div>
      {!valido && !invalido && !loading && (
        <p className="text-xs text-[var(--cor-texto-suave)]">{isLogradouro ? "Digite 8 dígitos do CEP para preencher automático — ou clique em Buscar." : "Digite 8 dígitos do CEP. Ex: 01310-100"}</p>
      )}
      {loading && <p className="flex items-center gap-1.5 text-xs text-[var(--cor-texto-suave)]"><Loader2 className="h-3 w-3 animate-spin" /> Buscando endereço…</p>}
      {erro && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro}</p>}
      {sugErro && <p role="alert" className="rounded-md border border-amber-500 bg-amber-50 px-3 py-2 text-sm text-amber-700">{sugErro}</p>}
      {resultado && (
        <div className="rounded-[var(--raio-md)] border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-0.5">
              <p className="flex items-center gap-1.5 text-sm font-medium text-[var(--cor-texto)]"><MapPin className="h-3.5 w-3.5 text-[var(--cor-primaria)]" />{resultado.logradouro || "—"}</p>
              <p className="text-xs text-[var(--cor-texto-suave)]">{resultado.bairro || "—"} · {resultado.localidade}/{resultado.uf} · CEP {resultado.cep}</p>
            </div>
            <Badge variant="outline" className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto)]">{resultado.uf}</Badge>
          </div>
          <Button size="sm" type="button" onClick={() => handleUsar(resultado)} className="mt-2 min-h-[36px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Usar este endereço</Button>
        </div>
      )}
    </div>
  );
}
