"use client"
import * as React from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Heart,
  HelpCircle,
  Image as ImageIcon,
  LayoutGrid,
  Megaphone,
  Newspaper,
  Radar,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react"

type Passo = {
  id: string
  titulo: string
  descricao: string
  dica: string
  Icon: React.ElementType
}

const PASSOS: Passo[] = [
  { id: "feed", titulo: "Sua capa, sua vibe", descricao: "O feed reúne as manchetes mais quentes em tempo real, sem enrolação.", dica: "Role, toque e mergulhe — as histórias te encontram.", Icon: Newspaper },
  { id: "categoria", titulo: "Explore por temas", descricao: "Filtre por política, economia, cultura e tudo que te interessa.", dica: "Toque na categoria e veja o assunto ganhar vida.", Icon: LayoutGrid },
  { id: "noticia", titulo: "Imagem + fonte = confiança", descricao: "Cada notícia mostra foto em destaque e a fonte original bem visível.", dica: "Toque na imagem para ampliar e confira a fonte antes de compartilhar.", Icon: ImageIcon },
  { id: "favoritos", titulo: "Seu feed, suas regras", descricao: "Favorite e personalize — salve o que ama e silencie o que não te representa.", dica: "Toque no coração e monte uma capa só sua.", Icon: Heart },
  { id: "comunidade", titulo: "Voz que conecta", descricao: "Comente, vote e troque ideias com quem vive a notícia.", dica: "Entre na conversa — sua opinião move a comunidade.", Icon: Users },
  { id: "radar", titulo: "Radar: o pulso do agora", descricao: "O radar mostra o que está bombando, com picos e tendências ao vivo.", dica: "Observe os sinais e antecipe o assunto do dia.", Icon: Radar },
  { id: "admin", titulo: "Central Admin", descricao: "Fila de checagem, robôs coletores, limites de uso e planos — tudo num só painel.", dica: "Se é admin, este é seu cockpit: fila, robôs, limites e planos.", Icon: ShieldCheck },
  { id: "monetizacao", titulo: "Apoie e monetize", descricao: "Entenda os espaços patrocinados e como o portal se mantém independente.", dica: "Identifique o selo 'patrocinado' — transparência total.", Icon: Megaphone },
]

export function TutorialTour() {
  const [open, setOpen] = React.useState(false)
  const [passo, setPasso] = React.useState(0)
  const [rect, setRect] = React.useState<DOMRect | null>(null)
  const atual = PASSOS[passo]
  const progresso = ((passo + 1) / PASSOS.length) * 100

  const atualizarSpotlight = React.useCallback(() => {
    const el = document.querySelector(`[data-tour="${PASSOS[passo]?.id}"]`)
    if (el) {
      const r = el.getBoundingClientRect()
      setRect(r)
      el.scrollIntoView({ behavior: "smooth", block: "center" })
    } else setRect(null)
  }, [passo])

  React.useEffect(() => {
    const visto = localStorage.getItem("tutorial_visto")
    const salvo = localStorage.getItem("tutorial_passo")
    if (salvo) {
      const n = parseInt(salvo, 10)
      if (!Number.isNaN(n) && n >= 0 && n < PASSOS.length) setPasso(n)
    }
    if (visto !== "true") {
      const t = setTimeout(() => setOpen(true), 800)
      return () => clearTimeout(t)
    }
  }, [])

  React.useEffect(() => {
    localStorage.setItem("tutorial_passo", String(passo))
  }, [passo])

  React.useEffect(() => {
    if (!open) return
    atualizarSpotlight()
    const h = () => atualizarSpotlight()
    window.addEventListener("resize", h)
    window.addEventListener("scroll", h, true)
    return () => {
      window.removeEventListener("resize", h)
      window.removeEventListener("scroll", h, true)
    }
  }, [open, atualizarSpotlight])

  React.useEffect(() => {
    const h = () => {
      setPasso(0)
      setOpen(true)
    }
    window.addEventListener("tutorial:abrir", h)
    return () => window.removeEventListener("tutorial:abrir", h)
  }, [])

  const fechar = React.useCallback((visto = false) => {
    setOpen(false)
    if (visto) localStorage.setItem("tutorial_visto", "true")
  }, [])

  const proximo = () => {
    if (passo === PASSOS.length - 1) fechar(true)
    else setPasso((p) => Math.min(p + 1, PASSOS.length - 1))
  }
  const anterior = () => setPasso((p) => Math.max(p - 1, 0))

  return (
    <>
      <button
        type="button"
        aria-label="Abrir tutorial"
        onClick={() => setOpen(true)}
        className="fixed bottom-20 right-4 z-[var(--z-cookies)] flex h-11 w-11 items-center justify-center rounded-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] shadow-[var(--sombra-3)] transition hover:bg-[var(--cor-primaria-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] md:bottom-6"
      >
        <HelpCircle className="h-5 w-5" />
      </button>

      <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : fechar(false))}>
        {open && (
          <div aria-hidden className="fixed inset-0 z-[var(--z-modal-fundo)] bg-[var(--cor-texto)]/60 backdrop-blur-[1px]" onClick={() => fechar(false)} />
        )}
        {/* ponytail: tour spotlight overlay — evoluir para driver.js quando lib for adicionada */}
        {open && rect && (
          <div
            aria-hidden
            className="pointer-events-none fixed z-[var(--z-modal-fundo)] rounded-[var(--raio-lg)] border-2 border-[var(--cor-primaria)] bg-transparent shadow-[0_0_0_9999px_rgba(0,0,0,0.55),0_0_24px_var(--cor-primaria)] transition-all duration-300"
            style={{ top: rect.top - 6, left: rect.left - 6, width: rect.width + 12, height: rect.height + 12 }}
          />
        )}
        <DialogContent
          className={cn(
            "z-[var(--z-modal)] max-h-[90vh] overflow-auto border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-0 sm:max-w-[420px]",
            rect ? "sm:translate-y-[-50%]" : ""
          )}
        >
          <div className="p-6 pb-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <Badge variant="secondary" className="gap-1 border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]">
                <Sparkles className="h-3 w-3" />
                {passo + 1} de {PASSOS.length}
              </Badge>
              <span className="flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]">
                <Check className="h-3 w-3 text-[var(--cor-primaria)]" />
                {Math.round(progresso)}% completo
              </span>
            </div>

            <Progress value={progresso} className="mb-4 h-1.5 bg-[var(--cor-skeleton-base)]" />

            <div className="mb-3 flex gap-1.5">
              {PASSOS.map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    "h-1.5 flex-1 rounded-full transition-colors",
                    i < passo ? "bg-[var(--cor-primaria)]" : i === passo ? "bg-[var(--cor-primaria)]" : "bg-[var(--cor-borda)]",
                    i <= passo && "opacity-100",
                    i > passo && "opacity-60"
                  )}
                />
              ))}
            </div>

            <div className="flex gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--raio-lg)] bg-[var(--gradiente-marca)] text-[var(--cor-texto-invertido)] shadow-[var(--sombra-1)]">
                <atual.Icon className="h-6 w-6" />
              </div>
              <div className="min-w-0 flex-1">
                <DialogTitle className="text-left text-[var(--cor-texto)]">{atual.titulo}</DialogTitle>
                <DialogDescription className="mt-1 text-left text-sm leading-relaxed text-[var(--cor-texto-suave)]">
                  {atual.descricao}
                </DialogDescription>
              </div>
            </div>

            <div className="mt-4 flex items-start gap-2 rounded-[var(--raio-md)] border border-dashed border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] px-3 py-2.5">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[var(--cor-primaria)]" />
              <p className="text-xs font-medium leading-relaxed text-[var(--cor-texto)]">
                Dica: <span className="font-normal text-[var(--cor-texto-suave)]">{atual.dica}</span>
              </p>
            </div>

            <div className="mt-4 flex flex-wrap gap-1.5">
              {PASSOS.map((p, i) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setPasso(i)}
                  aria-label={`Ir para ${p.titulo}`}
                  className={cn(
                    "flex h-7 w-7 items-center justify-center rounded-full border text-xs transition",
                    i === passo
                      ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                      : i < passo
                        ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]"
                        : "border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto-suave)]"
                  )}
                >
                  {i < passo ? <Check className="h-3.5 w-3.5" /> : i + 1}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between gap-2 border-t border-[var(--cor-borda)] bg-[var(--cor-fundo)] px-6 py-4">
            <Button variant="ghost" size="sm" onClick={() => fechar(true)} className="text-[var(--cor-texto-suave)]">
              Pular
            </Button>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={anterior} disabled={passo === 0} className="gap-1">
                <ChevronLeft className="h-4 w-4" />
                Anterior
              </Button>
              <Button size="sm" onClick={proximo} className="gap-1">
                {passo === PASSOS.length - 1 ? "Começar agora" : "Próximo"}
                {passo !== PASSOS.length - 1 && <ChevronRight className="h-4 w-4" />}
                {passo === PASSOS.length - 1 && <Sparkles className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
