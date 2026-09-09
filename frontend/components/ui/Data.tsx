import type { ReactNode } from "react";

// Cartão de indicador — espelha `.cartao-indicador` de globals.css.
export function StatCard({ rotulo, valor, detalhe }: { rotulo: string; valor: string; detalhe?: string }) {
  return (
    <div className="cartao-indicador">
      <p className="cartao-indicador__rotulo">{rotulo}</p>
      <p className="cartao-indicador__valor">{valor}</p>
      {detalhe && <p className="cartao-indicador__detalhe">{detalhe}</p>}
    </div>
  );
}

interface Coluna<T> {
  cabecalho: string;
  render: (linha: T) => ReactNode;
}

// Tabela responsiva (rolagem horizontal em `.tabela-wrapper`) com paginação
// acessível — botões com 40px mínimos e região identificada por `legenda`.
export function DataTable<T extends { id: number | string }>({
  colunas,
  linhas,
  legenda,
  pagina,
  totalPaginas,
  aoMudarPagina,
}: {
  colunas: Coluna<T>[];
  linhas: T[];
  legenda: string;
  pagina?: number;
  totalPaginas?: number;
  aoMudarPagina?: (pagina: number) => void;
}) {
  const temPaginacao =
    typeof pagina === "number" && typeof totalPaginas === "number" && aoMudarPagina;
  return (
    <div>
      <div className="tabela-wrapper">
        <table className="tabela">
          <caption className="visualmente-oculto">{legenda}</caption>
          <thead>
            <tr>
              {colunas.map((coluna) => (
                <th key={coluna.cabecalho} scope="col">
                  {coluna.cabecalho}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((linha) => (
              <tr key={linha.id}>
                {colunas.map((coluna) => (
                  <td key={coluna.cabecalho}>{coluna.render(linha)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {temPaginacao && aoMudarPagina && typeof pagina === "number" && typeof totalPaginas === "number" && (
        <nav className="paginacao" aria-label="Paginação">
          <button
            type="button"
            className="botao botao--fantasma botao--pequeno"
            style={{ minHeight: 40 }}
            disabled={pagina <= 1}
            onClick={() => aoMudarPagina(pagina - 1)}
          >
            Anterior
          </button>
          <span aria-current="page">
            Página {pagina} de {totalPaginas}
          </span>
          <button
            type="button"
            className="botao botao--fantasma botao--pequeno"
            style={{ minHeight: 40 }}
            disabled={pagina >= totalPaginas}
            onClick={() => aoMudarPagina(pagina + 1)}
          >
            Próxima
          </button>
        </nav>
      )}
    </div>
  );
}
