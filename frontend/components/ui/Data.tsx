import * as React from "react";
import { cn } from "@/lib/utils";

// shadcn Table primitives (inline, Tailwind) — overflow-x-auto + contain para mobile sem estouro
const Table = React.forwardRef<HTMLTableElement, React.HTMLAttributes<HTMLTableElement>>(
  ({ className, ...props }, ref) => (
    <div className="relative w-full overflow-x-auto rounded-lg border border-[var(--cor-borda)] [overscroll-behavior:contain]">
      <table ref={ref} className={cn("w-full min-w-[640px] caption-bottom text-sm", className)} {...props} />
    </div>
  )
);
Table.displayName = "Table";

const TableHeader = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => <thead ref={ref} className={cn("[&_tr]:border-b", className)} {...props} />
);
TableHeader.displayName = "TableHeader";

const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tbody ref={ref} className={cn("[&_tr:last-child]:border-0", className)} {...props} />
  )
);
TableBody.displayName = "TableBody";

const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn("border-b border-[var(--cor-borda)] transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted", className)}
      {...props}
    />
  )
);
TableRow.displayName = "TableRow";

const TableHead = React.forwardRef<HTMLTableCellElement, React.ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <th
      ref={ref}
      className={cn(
        "h-10 min-w-0 break-words px-4 text-left align-middle text-xs font-semibold uppercase tracking-wider text-[var(--cor-texto-suave)] [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
);
TableHead.displayName = "TableHead";

const TableCell = React.forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <td ref={ref} className={cn("min-w-0 break-words p-4 align-middle [&:has([role=checkbox])]:pr-0", className)} {...props} />
  )
);
TableCell.displayName = "TableCell";

const TableCaption = React.forwardRef<HTMLTableCaptionElement, React.HTMLAttributes<HTMLTableCaptionElement>>(
  ({ className, ...props }, ref) => (
    <caption ref={ref} className={cn("mt-4 text-sm text-[var(--cor-texto-suave)]", className)} {...props} />
  )
);
TableCaption.displayName = "TableCaption";

export function StatCard({ rotulo, valor, detalhe }: { rotulo: string; valor: string; detalhe?: string }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5 shadow-sm",
        "flex flex-col gap-1"
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--cor-texto-suave)]">{rotulo}</p>
      <p className="text-2xl font-bold tracking-tight text-[var(--cor-texto)]">{valor}</p>
      {detalhe && <p className="text-xs text-[var(--cor-texto-suave)]">{detalhe}</p>}
    </div>
  );
}

interface Coluna<T> {
  cabecalho: string;
  render: (linha: T) => React.ReactNode;
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
    <>
      <div className="-mx-4 overflow-x-auto px-4 [overscroll-behavior:contain] sm:mx-0 sm:px-0">
        <Table>
          <caption className="sr-only">{legenda}</caption>
          <TableHeader>
            <TableRow>
              {colunas.map((coluna) => (
                <TableHead key={coluna.cabecalho} scope="col">
                  {coluna.cabecalho}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {linhas.length === 0 ? (
              <TableRow>
                <TableCell colSpan={colunas.length} className="h-24 text-center text-[var(--cor-texto-suave)]">
                  Nenhum resultado encontrado…
                </TableCell>
              </TableRow>
            ) : (
              linhas.map((linha) => (
                <TableRow key={linha.id}>
                  {colunas.map((coluna) => (
                    <TableCell key={coluna.cabecalho}>{coluna.render(linha)}</TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      {typeof pagina === "number" && typeof totalPaginas === "number" && aoMudarPagina && (
        <nav
          className={cn("mt-4 flex items-center justify-center gap-4")}
          aria-label="Paginação"
        >
          <button
            type="button"
            className={cn(
              "inline-flex min-h-[44px] touch-manipulation items-center justify-center rounded-md border border-[var(--cor-borda)] bg-white px-4 text-sm font-medium",
              "hover:bg-[var(--cor-primaria-suave)] disabled:opacity-50 disabled:pointer-events-none",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
              "motion-reduce:transition-none transition-colors"
            )}
            disabled={pagina <= 1}
            onClick={() => aoMudarPagina(pagina - 1)}
          >
            Anterior
          </button>
          <span className="min-w-0 break-words text-sm text-[var(--cor-texto-suave)]" aria-current="page">
            Página {pagina} de {totalPaginas}
          </span>
          <button
            type="button"
            className={cn(
              "inline-flex min-h-[44px] touch-manipulation items-center justify-center rounded-md border border-[var(--cor-borda)] bg-white px-4 text-sm font-medium",
              "hover:bg-[var(--cor-primaria-suave)] disabled:opacity-50 disabled:pointer-events-none",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
              "motion-reduce:transition-none transition-colors"
            )}
            disabled={pagina >= totalPaginas}
            onClick={() => aoMudarPagina(pagina + 1)}
          >
            Próxima
          </button>
        </nav>
      )}
    </>
  );
}

export { Table, TableHeader, TableBody, TableHead, TableRow, TableCell, TableCaption };
