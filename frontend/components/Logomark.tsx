/**
 * Marca "Voz": duas aspas angulares — a voz de múltiplas fontes reunida
 * em uma só cobertura. Mesmo desenho do favicon (app/icon.tsx), em SVG
 * para reaproveitar nitidamente em qualquer tamanho na UI.
 */
export function Logomark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 512 512" className={className} aria-hidden focusable="false">
      <path
        d="M112.64 383.43 V256.00 Q112.64 149.81 240.07 128.57 V181.67 Q165.74 202.90 165.74 256.00 H229.45 V383.43 Z"
        fill="currentColor"
      />
      <path
        d="M271.93 383.43 V256.00 Q271.93 149.81 399.36 128.57 V181.67 Q325.03 202.90 325.03 256.00 H388.74 V383.43 Z"
        fill="currentColor"
        opacity="0.62"
      />
    </svg>
  );
}
