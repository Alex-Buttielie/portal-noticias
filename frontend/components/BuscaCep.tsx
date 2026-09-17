"use client";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { MapPin, Search, Loader2 } from "lucide-react";
import { buscarCep, buscarCepPorEndereco, normalizaCep, type EnderecoViaCep } from "@/lib/cep";

const UFS = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"];

function mascaraCep(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 8);
  if (d.length <= 5) return d;
  return `${d.slice(0, 5)}-${d.slice(5)}`;
}

function CartaoEndereco({ e, onUsar }: { e: EnderecoViaCep; onUsar?: (e: EnderecoViaCep) => void }) {
  return (
    <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-0.5">
          <p className="flex items-center gap-1.5 text-sm font-medium text-[var(--cor-texto)]"><MapPin className="h-3.5 w-3.5 text-[var(--cor-primaria)]" />{e.logradouro || "—"}</p>
          <p className="text-xs text-[var(--cor-texto-suave)]">{e.bairro || "—"} · {e.localidade}/{e.uf}</p>
          <p className="text-xs text-[var(--cor-texto-suave)]">CEP {e.cep}</p>
        </div>
        <Badge variant="outline" className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto)]">{e.uf}</Badge>
      </div>
      {onUsar && <Button size="sm" onClick={() => onUsar(e)} className="mt-2 min-h-[36px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Usar este endereço</Button>}
    </div>
  );
}

export default function BuscaCep({ onEndereco, valorInicial = "", compact = false }: { onEndereco?: (e: EnderecoViaCep) => void; valorInicial?: string; compact?: boolean }) {
  const [cep, setCep] = useState(() => mascaraCep(valorInicial));
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<EnderecoViaCep | null>(null);

  const [uf, setUf] = useState("");
  const [cidade, setCidade] = useState("");
  const [logradouro, setLogradouro] = useState("");
  const [loading2, setLoading2] = useState(false);
  const [erro2, setErro2] = useState<string | null>(null);
  const [resultados, setResultados] = useState<EnderecoViaCep[]>([]);

  const doBuscarCep = async () => {
    setErro(null); setResultado(null);
    const n = normalizaCep(cep);
    if (n.length !== 8) { setErro("CEP inválido. Informe 8 dígitos."); return; }
    setLoading(true);
    try { const e = await buscarCep(n); setResultado(e); } catch (e: unknown) { setErro(e instanceof Error ? e.message : "Falha ao buscar CEP."); } finally { setLoading(false); }
  };

  const doBuscarEndereco = async () => {
    setErro2(null); setResultados([]);
    setLoading2(true);
    try { const lista = await buscarCepPorEndereco(uf, cidade, logradouro); setResultados(lista); } catch (e: unknown) { setErro2(e instanceof Error ? e.message : "Falha ao buscar endereço."); } finally { setLoading2(false); }
  };

  return (
    <Card className={cn("border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]", compact && "shadow-none")}>
      <CardContent className={cn("p-4", compact && "p-3")}>
        <Tabs defaultValue="cep">
          <TabsList className="bg-[var(--cor-fundo-elevado)]">
            <TabsTrigger value="cep">Por CEP</TabsTrigger>
            <TabsTrigger value="endereco">Por endereço</TabsTrigger>
          </TabsList>

          <TabsContent value="cep" className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="busca-cep">CEP</Label>
              <div className="flex gap-2">
                <Input id="busca-cep" placeholder="00000-000" value={cep} onChange={e => setCep(mascaraCep(e.target.value))} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); doBuscarCep(); } }} inputMode="numeric" maxLength={9} className="bg-[var(--cor-fundo-card)]" aria-label="CEP" />
                <Button onClick={doBuscarCep} disabled={loading} className="min-h-[44px] min-w-[96px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  <span className="ml-1.5">{loading ? "Buscando…" : "Buscar"}</span>
                </Button>
              </div>
              <p className="text-xs text-[var(--cor-texto-suave)]">Digite 8 dígitos. Ex: 01310-100</p>
            </div>
            {erro && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro}</p>}
            {resultado && <CartaoEndereco e={resultado} onUsar={onEndereco} />}
          </TabsContent>

          <TabsContent value="endereco" className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label>UF</Label>
                <Select value={uf} onValueChange={setUf}>
                  <SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue placeholder="UF" /></SelectTrigger>
                  <SelectContent>{UFS.map(u => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="busca-cidade">Cidade</Label>
                <Input id="busca-cidade" placeholder="São Paulo" value={cidade} onChange={e => setCidade(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); doBuscarEndereco(); } }} className="bg-[var(--cor-fundo-card)]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="busca-logradouro">Logradouro</Label>
                <Input id="busca-logradouro" placeholder="Av. Paulista" value={logradouro} onChange={e => setLogradouro(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); doBuscarEndereco(); } }} className="bg-[var(--cor-fundo-card)]" />
              </div>
            </div>
            <Button onClick={doBuscarEndereco} disabled={loading2} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
              {loading2 ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              <span className="ml-1.5">{loading2 ? "Buscando…" : "Buscar endereços"}</span>
            </Button>
            {erro2 && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro2}</p>}
            {resultados.length > 0 && <div className="space-y-2">{resultados.map(r => <CartaoEndereco key={r.cep} e={r} onUsar={onEndereco} />)}</div>}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
