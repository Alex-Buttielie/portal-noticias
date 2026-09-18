"use client";
import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { Loader2, MapPin } from "lucide-react";
import { buscarCep, normalizaCep, type EnderecoViaCep } from "@/lib/cep";
import { listarEstados, listarMunicipios } from "@/lib/ibge";

const UFS_FALLBACK = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"];

export interface EnderecoForm {
  cep: string;
  uf: string;
  cidade: string;
  bairro: string;
  logradouro: string;
  numero: string;
  complemento: string;
}

type Props = {
  inicial?: Partial<EnderecoForm>;
  onEndereco?: (e: EnderecoForm, origem: EnderecoViaCep | null) => void;
  compact?: boolean;
  idPrefix?: string;
};

function mascaraCep(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 8);
  if (d.length <= 5) return d;
  return `${d.slice(0, 5)}-${d.slice(5)}`;
}

/**
 * FRENTE 5 — campo de endereço inteligente e reutilizável.
 * CEP com debounce+abort → preenche UF/cidade/bairro/logradouro;
 * UF/cidade com IBGE (proxy com cache, fallback direto); número e
 * complemento sempre manuais. Reaproveita lib/cep + lib/ibge.
 */
export default function EnderecoInteligente({ inicial, onEndereco, compact, idPrefix = "end-int" }: Props) {
  const [cep, setCep] = useState(() => (inicial?.cep ? mascaraCep(inicial.cep) : ""));
  const [uf, setUf] = useState(inicial?.uf ?? "");
  const [cidade, setCidade] = useState(inicial?.cidade ?? "");
  const [bairro, setBairro] = useState(inicial?.bairro ?? "");
  const [logradouro, setLogradouro] = useState(inicial?.logradouro ?? "");
  const [numero, setNumero] = useState(inicial?.numero ?? "");
  const [complemento, setComplemento] = useState(inicial?.complemento ?? "");
  const [ufs, setUfs] = useState<string[]>(UFS_FALLBACK);
  const [municipios, setMunicipios] = useState<string[]>([]);
  const [loadingCep, setLoadingCep] = useState(false);
  const [loadingMun, setLoadingMun] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [auto, setAuto] = useState(false);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abort = useRef<AbortController | null>(null);
  const primeira = useRef(true);

  // Emite o formulário consolidado (sem loops: montado a partir de estado).
  useEffect(() => {
    onEndereco?.({ cep: mascaraCep(cep), uf, cidade, bairro, logradouro, numero, complemento }, null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cep, uf, cidade, bairro, logradouro, numero, complemento]);

  // Estados (IBGE, cacheado) — uma vez.
  useEffect(() => {
    let vivo = true;
    listarEstados().then((l) => { if (vivo && l.length) setUfs(l.map((e) => e.sigla)); }).catch(() => {});
    return () => { vivo = false; };
  }, []);

  // Municípios quando a UF muda (pula o primeiro render).
  useEffect(() => {
    if (primeira.current) { primeira.current = false; return; }
    const u = uf.trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(u)) { setMunicipios([]); return; }
    let vivo = true;
    setLoadingMun(true);
    listarMunicipios(u)
      .then((l) => { if (vivo) setMunicipios(l); })
      .catch(() => { if (vivo) setMunicipios([]); })
      .finally(() => { if (vivo) setLoadingMun(false); });
    return () => { vivo = false; };
  }, [uf]);

  // CEP → autofill com debounce + abort de busca obsoleta.
  useEffect(() => {
    const n = normalizaCep(cep);
    if (n.length !== 8) {
      if (timer.current) clearTimeout(timer.current);
      abort.current?.abort();
      if (loadingCep) setLoadingCep(false);
      if (n.length === 0) { setErro(null); setAuto(false); }
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      abort.current?.abort();
      const ctrl = new AbortController();
      abort.current = ctrl;
      setLoadingCep(true); setErro(null);
      try {
        const e = await buscarCep(n, { signal: ctrl.signal });
        if (ctrl.signal.aborted) return;
        setUf(e.uf || "");
        setCidade(e.localidade || "");
        setBairro(e.bairro || "");
        setLogradouro(e.logradouro || "");
        setAuto(true);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setErro(err instanceof Error ? err.message : "Falha ao buscar CEP.");
        setAuto(false);
      } finally {
        if (abort.current === ctrl) setLoadingCep(false);
      }
    }, 500);
    return () => { if (timer.current) clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cep]);

  const nCep = normalizaCep(cep);
  const cepIncompleto = nCep.length > 0 && nCep.length < 8;
  const cepValido = nCep.length === 8 && !erro;

  async function buscarAgora() {
    if (timer.current) clearTimeout(timer.current);
    const n = normalizaCep(cep);
    if (n.length !== 8) { setErro("CEP incompleto. Informe 8 dígitos (ex: 01310-100)."); return; }
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setLoadingCep(true); setErro(null);
    try {
      const e = await buscarCep(n, { signal: ctrl.signal });
      if (ctrl.signal.aborted) return;
      setUf(e.uf || ""); setCidade(e.localidade || ""); setBairro(e.bairro || ""); setLogradouro(e.logradouro || "");
      setAuto(true);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setErro(err instanceof Error ? err.message : "Falha ao buscar CEP.");
    } finally {
      if (abort.current === ctrl) setLoadingCep(false);
    }
  }

  return (
    <div className={cn("space-y-3", compact && "space-y-2")}>
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-cep`}>CEP</Label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <MapPin className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-texto-suave)]" />
            <Input
              id={`${idPrefix}-cep`}
              value={cep}
              onChange={(e) => setCep(mascaraCep(e.target.value))}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); buscarAgora(); } }}
              placeholder="01310-100"
              inputMode="numeric"
              maxLength={9}
              autoComplete="postal-code"
              className={cn("bg-[var(--cor-fundo-card)] pl-8 transition-colors",
                erro ? "border-[var(--cor-erro)] focus-visible:ring-[var(--cor-erro)]" :
                cepValido ? "border-[var(--cor-sucesso)] focus-visible:ring-[var(--cor-sucesso)]" : "")}
              aria-invalid={!!erro}
              aria-describedby={`${idPrefix}-cep-hint`}
            />
            {loadingCep && <Loader2 className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-[var(--cor-texto-suave)]" />}
          </div>
          <Button type="button" onClick={buscarAgora} disabled={loadingCep} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
            {loadingCep ? "Buscando…" : "Buscar"}
          </Button>
        </div>
        <p id={`${idPrefix}-cep-hint`} className="text-xs text-[var(--cor-texto-suave)]">
          {loadingCep ? "Buscando endereço…" : cepIncompleto ? `Faltam ${8 - nCep.length} dígitos…` : auto ? "Preenchido automaticamente pelo CEP — ajuste se precisar." : "Digite 8 dígitos para preencher UF, cidade, bairro e rua."}
        </p>
      </div>

      <div aria-live="polite" aria-atomic="true">
        {erro && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro}</p>}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-uf`}>UF</Label>
          <Select value={uf} onValueChange={setUf}>
            <SelectTrigger id={`${idPrefix}-uf`} className="min-h-[44px] bg-[var(--cor-fundo-card)]"><SelectValue placeholder="UF" /></SelectTrigger>
            <SelectContent>{ufs.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-cidade`}>Cidade {loadingMun && <span className="font-normal text-[var(--cor-texto-suave)]">(carregando…)</span>}</Label>
          <Input
            id={`${idPrefix}-cidade`}
            value={cidade}
            onChange={(e) => setCidade(e.target.value)}
            placeholder="São Paulo"
            autoComplete="address-level2"
            list={municipios.length ? `${idPrefix}-mun` : undefined}
            className="min-h-[44px] bg-[var(--cor-fundo-card)]"
          />
          {municipios.length > 0 && (
            <datalist id={`${idPrefix}-mun`}>{municipios.slice(0, 200).map((m) => <option key={m} value={m} />)}</datalist>
          )}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-bairro`}>Bairro</Label>
          <Input id={`${idPrefix}-bairro`} value={bairro} onChange={(e) => setBairro(e.target.value)} placeholder="Bela Vista" autoComplete="address-level3" className="min-h-[44px] bg-[var(--cor-fundo-card)]" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-log`}>Logradouro</Label>
          <Input id={`${idPrefix}-log`} value={logradouro} onChange={(e) => setLogradouro(e.target.value)} placeholder="Av. Paulista" autoComplete="street-address" className="min-h-[44px] bg-[var(--cor-fundo-card)]" />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-num`}>Número</Label>
          <Input id={`${idPrefix}-num`} value={numero} onChange={(e) => setNumero(e.target.value)} placeholder="1000" inputMode="numeric" autoComplete="address-line2" className="min-h-[44px] bg-[var(--cor-fundo-card)]" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-comp`}>Complemento <span className="font-normal text-[var(--cor-texto-suave)]">(opcional)</span></Label>
          <Input id={`${idPrefix}-comp`} value={complemento} onChange={(e) => setComplemento(e.target.value)} placeholder="Apto 101" autoComplete="address-line3" className="min-h-[44px] bg-[var(--cor-fundo-card)]" />
        </div>
      </div>
    </div>
  );
}
