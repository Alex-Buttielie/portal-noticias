import type { ReactNode } from "react";

// Indicador de progresso com `role="status"` — leitor de tela anuncia sem roubar o foco.
export function LoadingSpinner({ rotulo = "Carregando…" }: { rotulo?: string }) {
  return (
    <p className="carregando" role="status">
      <span className="spinner" aria-hidden="true" /> {rotulo}
    </p>
  );
}

// Esqueleto no formato do cartão real (faixa 16/9 + 3 linhas) — evita salto de layout.
export function SkeletonCard() {
  return (
    <div className="cartao-noticia" aria-hidden="true">
      <div className="cartao-noticia__imagem esqueleto" style={{ aspectRatio: "16 / 9", minHeight: 0 }} />
      <div className="cartao-noticia__corpo">
        <div className="esqueleto esqueleto--linha-curta" />
        <div className="esqueleto esqueleto--linha" />
        <div className="esqueleto esqueleto--linha" />
      </div>
    </div>
  );
}

export function SkeletonLista({ quantidade = 3 }: { quantidade?: number }) {
  return (
    <div role="status" aria-label="Carregando conteúdo">
      {Array.from({ length: quantidade }, (_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

function MolduraEstado({ children, papel }: { children: ReactNode; papel?: "alert" }) {
  return (
    <div className="estado-vazio" role={papel}>
      <span aria-hidden="true" style={{ fontSize: "2rem", lineHeight: 1 }}>
        {papel === "alert" ? "⚠️" : "📰"}
      </span>
      {children}
    </div>
  );
}

export function EmptyState({ titulo, descricao }: { titulo: string; descricao?: string }) {
  return (
    <MolduraEstado>
      <p className="estado-vazio__titulo">{titulo}</p>
      {descricao && <p className="estado-vazio__descricao">{descricao}</p>}
    </MolduraEstado>
  );
}

export function ErrorState({ mensagem, aoTentarNovamente }: { mensagem: string; aoTentarNovamente?: () => void }) {
  return (
    <MolduraEstado papel="alert">
      <p className="estado-erro__titulo">Algo não saiu como esperado</p>
      <p className="estado-erro__descricao">{mensagem}</p>
      {aoTentarNovamente && (
        <button
          type="button"
          className="botao botao--secundaria botao--medio"
          style={{ minHeight: 40 }}
          onClick={aoTentarNovamente}
        >
          Tentar novamente
        </button>
      )}
    </MolduraEstado>
  );
}
