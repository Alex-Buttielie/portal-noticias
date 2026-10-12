"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

// Esta página é um Server Component (exporta `metadata`), então o guard de
// login não pode viver direto em page.tsx — precisa de um client component
// próprio, como as demais islands desta pasta (FontesIsland, PremiumFlagIsland).
export function GuardAdminIsland() {
  const { token, carregando } = useAuth();
  const r = useRouter();

  useEffect(() => {
    if (!carregando && !token) r.replace("/login");
  }, [carregando, token, r]);

  return null;
}
