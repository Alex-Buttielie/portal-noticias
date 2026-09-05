"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const ATALHOS = [
  { label: "Últimas", href: "/" },
  { label: "Política", href: "/?categoria=política" },
  { label: "Economia", href: "/?categoria=economia" },
  { label: "Esportes", href: "/?categoria=esportes" },
  { label: "Tecnologia", href: "/?categoria=tecnologia" },
  { label: "Comunidade", href: "/comunidade" },
  { label: "Radar", href: "/radar" },
  { label: "Premium", href: "/planos" },
];

export default function CommandPalette({ aberto, aoFechar }: { aberto: boolean; aoFechar: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!aberto) setQ("");
  }, [aberto]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") aoFechar();
    }
    if (aberto) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [aberto, aoFechar]);

  if (!aberto) return null;

  const filtrados = q.trim()
    ? ATALHOS.filter((a) => a.label.toLowerCase().includes(q.toLowerCase()))
    : ATALHOS;

  function ir(href: string) {
    aoFechar();
    router.push(href);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const t = q.trim();
    if (!t) return;
    const hit = filtrados[0];
    if (hit && hit.label.toLowerCase() === t.toLowerCase()) ir(hit.href);
    else ir(`/?busca=${encodeURIComponent(t)}`);
  }

  return (
    <div className="palette-fundo" onClick={aoFechar} role="presentation">
      <div className="palette" role="dialog" aria-modal="true" aria-label="Busca rápida" onClick={(e) => e.stopPropagation()}>
        <form onSubmit={onSubmit} className="palette-busca">
          <span aria-hidden>⌕</span>
          <input autoFocus placeholder="Buscar notícias, editorias…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar" />
          <kbd>↵</kbd>
        </form>
        <div className="palette-lista" role="listbox">
          {filtrados.map((a) => (
            <button key={a.href} type="button" role="option" className="palette-item" onClick={() => ir(a.href)}>
              <span className="palette-item-label">{a.label}</span>
              <span className="palette-item-hint">{a.href}</span>
            </button>
          ))}
          {filtrados.length === 0 && <p className="texto-suave" style={{ padding: "1rem" }}>Nenhum atalho — pressione Enter para buscar “{q}”.</p>}
        </div>
        <p className="palette-rodape texto-suave">↵ buscar · Esc fechar · ⌘K reabrir</p>
      </div>
    </div>
  );
}
