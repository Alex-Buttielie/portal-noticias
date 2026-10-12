/**
 * Marca "Voz": duas aspas angulares — a voz de múltiplas fontes reunida
 * em uma só cobertura. Mesmo desenho do favicon (app/icon.tsx), em SVG
 * para reaproveitar nitidamente em qualquer tamanho na UI.
 */
export function Logomark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden focusable="false">
      <path d="M6 30V18Q6 8 18 6V11Q11 13 11 18H17V30Z" fill="currentColor" />
      <path d="M21 30V18Q21 8 33 6V11Q26 13 26 18H32V30Z" fill="currentColor" opacity="0.62" />
    </svg>
  );
}
