export function LoadingSpinner({ rotulo = "Carregando…" }: { rotulo?: string }) {
  return (
    <p className="carregando" role="status">
      <span className="spinner" aria-hidden="true" /> {rotulo}
    </p>
  );
}

export function SkeletonCard() {
  return (
    <div className="cartao-noticia cartao-noticia--esqueleto" aria-hidden="true">
      <div className="cartao-noticia__imagem esqueleto" />
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

export function EmptyState({ titulo, descricao }: { titulo: string; descricao?: string }) {
  return (
    <div className="estado-vazio">
      <p className="estado-vazio__titulo">{titulo}</p>
      {descricao && <p className="estado-vazio__descricao">{descricao}</p>}
    </div>
  );
}

export function ErrorState({ mensagem, aoTentarNovamente }: { mensagem: string; aoTentarNovamente?: () => void }) {
  return (
    <div className="estado-erro" role="alert">
      <p className="estado-erro__titulo">Algo não saiu como esperado</p>
      <p className="estado-erro__descricao">{mensagem}</p>
      {aoTentarNovamente && (
        <button type="button" className="botao botao--secundaria botao--medio" onClick={aoTentarNovamente}>
          Tentar novamente
        </button>
      )}
    </div>
  );
}
