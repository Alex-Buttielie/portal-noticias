"use client";

import * as React from "react";
import {
  flexRender,
  type PaginationState,
  type RowData,
  type SortingState,
} from "@tanstack/react-table";
import {
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useLegacyTable,
  type LegacyColumnDef,
} from "@tanstack/react-table/legacy";
import { ChevronsLeft, ChevronsRight, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Input } from "./input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select";

export interface DataTableProps<TData extends RowData> {
  columns: LegacyColumnDef<TData, unknown>[];
  data: TData[];
  pageSize?: number;
  searchable?: boolean;
  filterable?: boolean;
  onRowClick?: (row: TData) => void;
  searchKey?: string;
  filterKey?: string;
  searchPlaceholder?: string;
}

function lerQuery(key: string | undefined): string {
  if (!key || typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get(key) ?? "";
}

function lerPagina(): number {
  if (typeof window === "undefined") return 0;
  const raw = new URLSearchParams(window.location.search).get("pagina");
  const n = raw ? Number.parseInt(raw, 10) - 1 : 0;
  return Number.isNaN(n) || n < 0 ? 0 : n;
}

export function DataTable<TData extends RowData>({
  columns,
  data,
  pageSize = 10,
  searchable = true,
  filterable = false,
  onRowClick,
  searchKey,
  filterKey,
  searchPlaceholder = "Buscar…",
}: DataTableProps<TData>) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = React.useState<string>(() => lerQuery(searchKey));
  const [columnFilter, setColumnFilter] = React.useState<string>(() => lerQuery(filterKey));
  const [pagination, setPagination] = React.useState<PaginationState>(() => ({
    pageIndex: lerPagina(),
    pageSize,
  }));

  const table = useLegacyTable({
    data,
    columns,
    state: {
      sorting,
      globalFilter,
      columnFilters: filterKey && columnFilter ? [{ id: filterKey, value: columnFilter }] : [],
      pagination,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: (value) => {
      setGlobalFilter(typeof value === "string" ? value : "");
      setPagination((prev) => ({ ...prev, pageIndex: 0 }));
    },
    onColumnFiltersChange: (updater) => {
      const next = typeof updater === "function" ? updater([]) : updater;
      const found = next.find((f) => f.id === filterKey);
      setColumnFilter(typeof found?.value === "string" ? found.value : "");
      setPagination((prev) => ({ ...prev, pageIndex: 0 }));
    },
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (searchKey) {
      if (globalFilter) params.set(searchKey, globalFilter);
      else params.delete(searchKey);
    }
    if (filterKey) {
      if (columnFilter) params.set(filterKey, columnFilter);
      else params.delete(filterKey);
    }
    if (pagination.pageIndex > 0) params.set("pagina", String(pagination.pageIndex + 1));
    else params.delete("pagina");
    const query = params.toString();
    window.history.replaceState({}, "", query ? `${window.location.pathname}?${query}` : window.location.pathname);
  }, [globalFilter, columnFilter, pagination.pageIndex, searchKey, filterKey]);

  const pageCount = table.getPageCount();
  const canPrevious = table.getCanPreviousPage();
  const canNext = table.getCanNextPage();

  return (
    <div className="w-full space-y-4">
      {(searchable || (filterable && filterKey)) && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {searchable && (
            <div className="relative max-w-xs flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-texto-suave)]" aria-hidden="true" />
              <label htmlFor="datatable-busca" className="sr-only">
                Buscar na tabela
              </label>
              <Input
                id="datatable-busca"
                name="busca"
                type="search"
                inputMode="text"
                placeholder={searchPlaceholder}
                value={globalFilter}
                onChange={(e) => table.setGlobalFilter(e.target.value)}
                className="pl-10 text-[16px] sm:text-sm"
              />
            </div>
          )}
          {filterable && filterKey && (
            <div className="max-w-xs flex-1">
              <label htmlFor="datatable-filtro" className="sr-only">
                Filtrar coluna
              </label>
              <Input
                id="datatable-filtro"
                name="filtro"
                type="search"
                inputMode="text"
                placeholder="Filtrar…"
                value={columnFilter}
                onChange={(e) => table.getColumn(filterKey)?.setFilterValue(e.target.value)}
                className="text-[16px] sm:text-sm"
              />
            </div>
          )}
        </div>
      )}

      <div className="overflow-hidden rounded-md border border-[var(--cor-borda)]">
        <table className="w-full caption-bottom text-sm">
          <thead className="[&_tr]:border-b [&_tr]:border-[var(--cor-borda)]">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"}
                      className="h-12 px-4 text-left align-middle font-medium text-[var(--cor-texto-suave)]"
                    >
                      {header.isPlaceholder ? null : header.column.getCanSort() ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          aria-label={
                            sorted === "asc"
                              ? "Ordenar decrescente"
                              : sorted === "desc"
                                ? "Remover ordenação"
                                : "Ordenar crescente"
                          }
                          className={cn(
                            "inline-flex min-h-[44px] touch-manipulation items-center gap-2 rounded-sm hover:text-[var(--cor-primaria)]",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                            "motion-reduce:transition-none"
                          )}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {sorted === "asc" ? (
                            <ChevronUp className="h-4 w-4" aria-hidden="true" />
                          ) : sorted === "desc" ? (
                            <ChevronDown className="h-4 w-4" aria-hidden="true" />
                          ) : null}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="[&_tr:last-child]:border-0">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="h-24 text-center text-[var(--cor-texto-suave)]">
                  Nenhum resultado encontrado.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={cn(
                    "border-b border-[var(--cor-borda)]",
                    onRowClick && "cursor-pointer hover:bg-[var(--cor-primaria-suave)]/50"
                  )}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onRowClick(row.original);
                          }
                        }
                      : undefined
                  }
                  tabIndex={onRowClick ? 0 : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="p-4 align-middle">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
        <div className="flex items-center gap-2">
          <span className="text-sm text-[var(--cor-texto-suave)]" aria-live="polite">
            Página {pagination.pageIndex + 1} de {Math.max(pageCount, 1)}
          </span>
          <label htmlFor="datatable-page-size" className="sr-only">
            Itens por página
          </label>
          <Select
            value={`${pagination.pageSize}`}
            onValueChange={(value) => table.setPageSize(Number(value))}
          >
            <SelectTrigger id="datatable-page-size" className="w-[70px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[10, 20, 30, 40, 50].map((size) => (
                <SelectItem key={size} value={`${size}`}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            onClick={() => table.setPageIndex(0)}
            disabled={!canPrevious}
            aria-label="Primeira página"
          >
            <ChevronsLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => table.previousPage()}
            disabled={!canPrevious}
            aria-label="Página anterior"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => table.nextPage()}
            disabled={!canNext}
            aria-label="Próxima página"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => table.setPageIndex(pageCount - 1)}
            disabled={!canNext}
            aria-label="Última página"
          >
            <ChevronsRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}
