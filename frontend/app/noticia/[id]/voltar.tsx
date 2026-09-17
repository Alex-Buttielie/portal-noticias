"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
export function Voltar({ categoria }: { categoria: string }) {
  const router = useRouter();
  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={() => { if (typeof window !== "undefined" && window.history.length > 1) router.back(); else router.push("/"); }} className="inline-flex min-h-[36px] items-center rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">← Voltar</button>
      <Link href={`/categoria/${encodeURIComponent(categoria)}`} className="text-xs capitalize text-[var(--cor-primaria)] hover:underline">ver {categoria} →</Link>
    </div>
  );
}
