"use client";

import * as React from "react";
import type { LegacyColumnDef } from "@tanstack/react-table/legacy";
import type { RowData } from "@tanstack/react-table";
import { DataTable as CanonicalDataTable, type DataTableProps as CanonicalProps } from "./data-table";

// Formato simples legado (ex.: `app/comunidade/page.tsx`).
export interface SimpleColumn<TData> {
  id: string;
  header: string;
  accessorKey?: keyof TData & string;
  cell?: (row: TData) => React.ReactNode;
  enableSorting?: boolean;
}

export interface SimpleDataTableProps<TData extends RowData>
  extends Omit<CanonicalProps<TData>, "columns"> {
  columns: SimpleColumn<TData>[];
}

function adaptar<TData extends RowData>(colunas: SimpleColumn<TData>[]): LegacyColumnDef<TData, unknown>[] {
  return colunas.map(
    (coluna): LegacyColumnDef<TData, unknown> => ({
      id: coluna.id,
      header: coluna.header,
      enableSorting: coluna.enableSorting ?? coluna.accessorKey !== undefined,
      accessorFn: (row) => (row as Record<string, unknown>)[coluna.id],
      cell: coluna.cell ? (info) => coluna.cell?.(info.row.original) : undefined,
    })
  );
}

export function DataTable<TData extends RowData>({ columns, ...rest }: SimpleDataTableProps<TData>) {
  const adaptadas = React.useMemo(() => adaptar(columns), [columns]);
  return <CanonicalDataTable columns={adaptadas} {...rest} />;
}
