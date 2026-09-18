import { BarChart3, MessagesSquare, MessageSquare, MessageSquareQuote, Newspaper } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * FRENTE 4 (Comunidade viva) — identidade jornalística dos formatos.
 * Diferenciação visual explícita: notícia vs coluna/análise vs opinião vs
 * comentário vs discussão (cor + ícone + rótulo + borda lateral do cartão).
 */
export type FormatoComunidade = "noticia" | "coluna" | "opiniao" | "comentario" | "discussao";

const MAPA: Record<FormatoComunidade, { rotulo: string; selo: string; barra: string; Icone: typeof Newspaper }> = {
  noticia: {
    rotulo: "Notícia",
    selo: "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-200",
    barra: "border-l-sky-500",
    Icone: Newspaper,
  },
  coluna: {
    rotulo: "Coluna",
    selo: "border-violet-300 bg-violet-50 text-violet-800 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-200",
    barra: "border-l-violet-500",
    Icone: BarChart3,
  },
  opiniao: {
    rotulo: "Opinião",
    selo: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200",
    barra: "border-l-amber-500",
    Icone: MessageSquareQuote,
  },
  comentario: {
    rotulo: "Comentário",
    selo: "border-zinc-300 bg-zinc-50 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300",
    barra: "border-l-zinc-400",
    Icone: MessageSquare,
  },
  discussao: {
    rotulo: "Discussão",
    selo: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
    barra: "border-l-emerald-500",
    Icone: MessagesSquare,
  },
};

/** "analise" do backend é exibida como Coluna; resto mapeia direto. */
export function formatoDaPublicacao(tipo: string, numeroComentarios = 0): FormatoComunidade {
  if (tipo === "analise") return "coluna";
  if (tipo === "opiniao" && numeroComentarios >= 3) return "discussao";
  if (tipo === "opiniao") return "opiniao";
  return "discussao";
}

export function barraPorFormato(formato: FormatoComunidade): string {
  return MAPA[formato].barra;
}

export function SeloFormato({ formato, className }: { formato: FormatoComunidade; className?: string }) {
  const { rotulo, selo, Icone } = MAPA[formato];
  return (
    <Badge variant="outline" className={cn("gap-1 text-[11px] font-semibold", selo, className)}>
      <Icone className="h-3 w-3" aria-hidden />
      {rotulo}
    </Badge>
  );
}
