"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { alternarSalvo, estaSalvo, chaveDoSalvo } from "@/lib/bookmarks";
import { registrarLeitura } from "@/lib/intent";
import { trackSave, trackShare } from "@/lib/analytics";
import type { FeedEntrada } from "@/lib/api";
import { Bookmark, BookmarkCheck, Share2, Copy, Check, Crown, ExternalLink } from "lucide-react";
export function AcoesNoticia({ entrada }: { entrada: FeedEntrada }) {
  const [salvo, setSalvo] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [premiumOpen, setPremiumOpen] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const [url, setUrl] = useState("");
  useEffect(() => { setSalvo(estaSalvo(entrada)); registrarLeitura(entrada.categoria); if(typeof window!=="undefined") setUrl(window.location.href); }, [entrada]);
  function onSave() { const n = alternarSalvo(entrada); setSalvo(n); if(n) setSaveOpen(true); if(n) trackSave(entrada.tipo === "cluster" ? "cluster" : "item", entrada.id, entrada.categoria); }
  async function copiar(){ try{ await navigator.clipboard.writeText(url); setCopiado(true); setTimeout(()=>setCopiado(false),2000);}catch{} trackShare(entrada.tipo === "cluster" ? "cluster" : "item", entrada.id, entrada.categoria); }
  async function nativo(){ const data={title:entrada.titulo,text:entrada.resumo,url}; try{ if(navigator.share) { await navigator.share(data); trackShare(entrada.tipo === "cluster" ? "cluster" : "item", entrada.id, entrada.categoria); } else await copiar(); }catch{} }
  const encUrl=encodeURIComponent(url); const encTitulo=encodeURIComponent(entrada.titulo);
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={onSave} aria-pressed={salvo} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] min-h-[44px]">
          <Bookmark className="mr-1 h-4 w-4" fill={salvo ? "currentColor" : "none"} /> {salvo ? "Salvo" : "Salvar"}
        </Button>
        <Button variant="outline" onClick={()=>setShareOpen(true)} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] min-h-[44px]">
          <Share2 className="mr-1 h-4 w-4" /> Compartilhar
        </Button>
        <Button variant="outline" onClick={()=>setPremiumOpen(true)} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] min-h-[44px] text-[var(--cor-texto-suave)]">
          <Crown className="mr-1 h-4 w-4 text-[var(--cor-primaria)]" /> Premium
        </Button>
        <span className="sr-only" aria-live="polite">{chaveDoSalvo(entrada)}</span>
      </div>

      <Dialog open={shareOpen} onOpenChange={setShareOpen}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle>Compartilhar</DialogTitle>
            <DialogDescription>Escolha como compartilhar esta notícia.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input readOnly value={url} className="flex-1 border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-sm" aria-label="Link da notícia" />
              <Button onClick={copiar} variant="outline" className="min-h-[44px] shrink-0 border-[var(--cor-borda)]">
                {copiado ? <Check className="h-4 w-4 text-[var(--cor-sucesso)]" /> : <Copy className="h-4 w-4" />} {copiado ? "Copiado!" : "Copiar"}
              </Button>
            </div>
            <Button onClick={nativo} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">
              <Share2 className="mr-2 h-4 w-4" /> Compartilhar no aparelho
            </Button>
            <div className="grid grid-cols-3 gap-2">
              <a href={`https://wa.me/?text=${encTitulo}%20${encUrl}`} target="_blank" rel="noopener noreferrer" onClick={() => trackShare(entrada.tipo === "cluster" ? "cluster" : "item", entrada.id, entrada.categoria)} className="inline-flex min-h-[44px] items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-elevado)]">WhatsApp</a>
              <a href={`https://twitter.com/intent/tweet?text=${encTitulo}&url=${encUrl}`} target="_blank" rel="noopener noreferrer" onClick={() => trackShare(entrada.tipo === "cluster" ? "cluster" : "item", entrada.id, entrada.categoria)} className="inline-flex min-h-[44px] items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-elevado)]">X / Twitter</a>
              <a href={`https://www.facebook.com/sharer/sharer.php?u=${encUrl}`} target="_blank" rel="noopener noreferrer" onClick={() => trackShare(entrada.tipo === "cluster" ? "cluster" : "item", entrada.id, entrada.categoria)} className="inline-flex min-h-[44px] items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-elevado)]">Facebook</a>
            </div>
            {copiado && <p role="status" className="text-xs text-[var(--cor-sucesso)]">Link copiado para a área de transferência.</p>}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader className="items-center text-center sm:items-center sm:text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]"><BookmarkCheck className="h-6 w-6" /></div>
            <DialogTitle className="text-center">Salvo nos favoritos!</DialogTitle>
            <DialogDescription className="text-center">Você pode acessar esta notícia a qualquer momento nos seus favoritos.</DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            <Button asChild className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]"><Link href="/favoritos"><ExternalLink className="mr-2 h-4 w-4" /> Ver favoritos</Link></Button>
            <Button variant="outline" onClick={()=>setSaveOpen(false)} className="w-full min-h-[44px]">Continuar lendo</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={premiumOpen} onOpenChange={setPremiumOpen}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Crown className="h-5 w-5 text-[var(--cor-primaria)]" /> Conteúdo Premium</DialogTitle>
            <DialogDescription>Assine para liberar o acesso completo.</DialogDescription>
          </DialogHeader>
          <ul className="space-y-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-sm text-[var(--cor-texto)]">
            <li className="flex gap-2"><Check className="h-4 w-4 shrink-0 text-[var(--cor-primaria)]" /> Sem anúncios em todo o site</li>
            <li className="flex gap-2"><Check className="h-4 w-4 shrink-0 text-[var(--cor-primaria)]" /> Feed personalizado e Radar avançado</li>
            <li className="flex gap-2"><Check className="h-4 w-4 shrink-0 text-[var(--cor-primaria)]" /> Newsletter exclusiva e arquivo completo</li>
          </ul>
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            <Button asChild className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]"><Link href="/planos">Ver planos</Link></Button>
            <Button variant="ghost" onClick={()=>setPremiumOpen(false)} className="w-full min-h-[44px]">Agora não</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
