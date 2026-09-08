import type { ReactNode } from "react";

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
  return (
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
      {typeof pagina === "number" && typeof totalPaginas === "number" && aoMudarPagina && (
        <nav className="paginacao" aria-label="Paginação">
          <button
            type="button"
            className="botao botao--fantasma botao--pequeno"
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
