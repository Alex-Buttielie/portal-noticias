"use client";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const atual = theme ?? resolvedTheme ?? "light";
  if (!mounted) return <button type="button" aria-label="Alternar tema" className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]" />;
  const proximo = atual === "dark" ? "light" : "dark";
  return (
    <button type="button" aria-label={`Ativar tema ${proximo}`} onClick={() => setTheme(proximo)} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto)] transition-colors hover:bg-[var(--cor-borda)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-reduce:transition-none">
      <Sun className="h-4 w-4 transition-opacity motion-reduce:transition-none" style={{ display: atual === "dark" ? "none" : "block" }} aria-hidden />
      <Moon className="h-4 w-4 transition-opacity motion-reduce:transition-none" style={{ display: atual === "dark" ? "block" : "none" }} aria-hidden />
    </button>
  );
}
