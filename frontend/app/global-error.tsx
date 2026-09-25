"use client";

import { useEffect } from "react";

/**
 * Error boundary da RAIZ (critério 4).
 *
 * `global-error.tsx` só érenderizado quando a falha acontece no próprio layout
 * raiz (ou seja, fora do `<Providers>`): por isso ele precisa desenhar
 * `<html>`/`<body>` e não pode usar nenhum componente que dependa de contexto
 * deProviders (React Query, tema, toasts, banner de consentimento) — todos
 * quebraram junto com o layout.
 *
 * Consequência aceita: aqui não há `Link` do Next nem os componentes do design
 * system, porque qualquer um deles que dependa do Providers reentraria em
 * loop. O texto é propositalmente curto e o código de correlência, quando
 * existe, é exibido em texto puro para ser copiado.
 */
export default function ErroGlobal({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[erro-global]", {
      nome: error?.name,
      mensagem: error?.message,
      digest: error?.digest ?? null,
    });
  }, [error]);

  return (
    <html lang="pt-BR">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#FDFBF7",
          color: "#1A1A1A",
          fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
          padding: "1.5rem",
        }}
      >
        <main style={{ maxWidth: "40rem", width: "100%" }} role="alert">
          <p style={{ fontSize: "0.75rem", letterSpacing: "0.2em", margin: 0, opacity: 0.7 }}>ERRO</p>
          <h1 style={{ fontSize: "1.5rem", lineHeight: 1.3, margin: "0.5rem 0" }}>
            O portal encontrou um erro grave
          </h1>
          <p style={{ margin: 0, opacity: 0.85 }}>
            A estrutura da aplicação não pôde ser montada, então o restante do portal pode estar indisponível.
            Tente recarregar.
          </p>
          {error?.digest ? (
            <p style={{ marginTop: "1rem", fontSize: "0.8rem", opacity: 0.8 }}>
              Código de suporte (servidor): <code style={{ wordBreak: "break-all" }}>{error.digest}</code>
            </p>
          ) : null}
          <div style={{ marginTop: "1.5rem" }}>
            <button
              type="button"
              onClick={() => reset()}
              style={{
                minHeight: "44px",
                padding: "0 1rem",
                borderRadius: "0.375rem",
                border: "1px solid #0A84FF",
                background: "#0A84FF",
                color: "#fff",
                fontSize: "0.9rem",
                cursor: "pointer",
              }}
            >
              Tentar de novo
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
