"use client"
import * as React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
export type CalendarProps = { className?: string; selected?: Date; onSelect?: (d: Date | undefined) => void; disabled?: (d: Date) => boolean; mode?: string }
function Calendar({ className, selected, onSelect, disabled }: CalendarProps) {
  const [cur, setCur] = React.useState(() => selected ?? new Date())
  const y = cur.getFullYear(); const m = cur.getMonth()
  const first = new Date(y, m, 1).getDay(); const days = new Date(y, m + 1, 0).getDate()
  const cells: (number | null)[] = Array(first).fill(null).concat(Array.from({ length: days }, (_, i) => i + 1))
  while (cells.length % 7 !== 0) cells.push(null)
  const fmt = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" })
  return (
    <div className={cn("p-3 bg-[var(--cor-fundo-card)] border border-[var(--cor-borda)] rounded-[var(--raio-lg)] shadow-[var(--sombra-1)]", className)}>
      <div className="flex items-center justify-between mb-2">
        <Button variant="ghost" size="icon" onClick={() => setCur(new Date(y, m - 1, 1))} aria-label="Mes anterior"><ChevronLeft className="h-4 w-4" /></Button>
        <span className="text-sm font-medium text-[var(--cor-texto)] capitalize">{fmt.format(cur)}</span>
        <Button variant="ghost" size="icon" onClick={() => setCur(new Date(y, m + 1, 1))} aria-label="Proximo mes"><ChevronRight className="h-4 w-4" /></Button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-[var(--cor-texto-suave)] mb-1"><span>D</span><span>S</span><span>T</span><span>Q</span><span>Q</span><span>S</span><span>S</span></div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((d, i) => {
          if (d === null) return <span key={i} />
          const date = new Date(y, m, d); const isSel = selected && date.toDateString() === selected.toDateString(); const isDis = disabled?.(date)
          return <button key={i} disabled={!!isDis} onClick={() => onSelect?.(date)} className={cn("h-8 w-8 rounded-[var(--raio-sm)] text-sm flex items-center justify-center transition-colors disabled:opacity-30", isSel ? "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" : "hover:bg-[var(--cor-borda)] text-[var(--cor-texto)]")}>{d}</button>
        })}
      </div>
    </div>
  )
}
Calendar.displayName = "Calendar"
export { Calendar }
