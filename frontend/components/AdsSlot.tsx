import { cn } from "@/lib/utils";

type Formato = "horizontal" | "retangulo" | "vertical" | "in-feed";

const ALTURA: Record<Formato, string> = {
  horizontal: "90px",
  retangulo: "250px",
  vertical: "600px",
  "in-feed": "200px",
};

export function AdsSlot({
  id,
  formato,
  className,
  rotulo,
}: {
  id: string;
  formato: Formato;
  className?: string;
  rotulo?: string;
}) {
  return (
    // ponytail: AdsSlot placeholder div — trocar por <ins class='adsbygoogle' data-ad-client=...> quando tiver publisher ID + script adsbygoogle.js em layout.tsx.
    <div
      role="complementary"
      aria-label={`Publicidade ${id}`}
      className={cn(
        "relative flex flex-col items-center justify-center overflow-hidden rounded-[var(--raio-lg)] border border-dashed bg-[var(--cor-fundo-elevado)] p-4 text-center",
        className
      )}
      style={{ minHeight: ALTURA[formato], borderColor: "var(--cor-borda)" }}
    >
      <div className="hud-grid absolute inset-0 opacity-[0.12]" aria-hidden />
      <div className="relative flex flex-col items-center gap-1">
        <span className="text-[10px] font-medium tracking-[0.14em] text-[var(--cor-texto-suave)]">
          PUBLICIDADE{rotulo ? ` • ${rotulo.toUpperCase()}` : ""}
        </span>
        <span className="max-w-[28ch] text-balance text-sm font-medium leading-tight text-[var(--cor-texto-suave)]">
          Anúncio — Google AdSense (slot {id})
        </span>
        <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2.5 py-0.5 text-[10px] tracking-wide text-[var(--cor-texto-suave)]">
          Conteúdo publicitário
        </span>
      </div>
    </div>
  );
}
