/** Estado de carregamento fluido: evita o salto abrupto de "Carregando..."
 * para o conteúdo final, mantendo o layout (grade de cartões) estável. */
export default function CartaoEsqueleto() {
  return (
    <div className="esqueleto-cartao" aria-hidden="true">
      <span className="esqueleto esqueleto-linha" style={{ width: "40%" }} />
      <span className="esqueleto esqueleto-linha" style={{ width: "90%", height: "1.1rem" }} />
      <span className="esqueleto esqueleto-linha" style={{ width: "100%" }} />
      <span className="esqueleto esqueleto-linha" style={{ width: "60%" }} />
    </div>
  );
}
