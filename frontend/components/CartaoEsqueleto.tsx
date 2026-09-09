// Estado de carregamento fluido no formato do cartão real (faixa 16/9 +
// linhas) — evita o salto de "Carregando..." para o conteúdo final e mantém
// a grade estável. Mesma API (sem props), só classes do design system v2.
export default function CartaoEsqueleto() {
  return (
    <div className="cartao-noticia" aria-hidden="true">
      <div className="cartao-noticia__imagem esqueleto" style={{ aspectRatio: "16 / 9", minHeight: 0 }} />
      <div className="cartao-noticia__corpo">
        <span className="esqueleto esqueleto--linha-curta" />
        <span className="esqueleto esqueleto--linha" />
        <span className="esqueleto esqueleto--linha" />
      </div>
    </div>
  );
}
